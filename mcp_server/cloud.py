"""Cloud HTTP transport for the MCP server.

Cursor Cloud Agents speak Streamable HTTP (not SSE). Local desktop still
defaults to stdio. This module resolves bind/auth settings and applies them
to a FastMCP instance before ``mcp.run(transport="streamable-http")``.
"""
from __future__ import annotations

import argparse
import hmac
import os
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

TransportName = Literal["stdio", "streamable-http"]

_HTTP_ALIASES = {"streamable-http", "http", "cloud", "remote"}
_STDIO_ALIASES = {"stdio", "local", ""}


@dataclass(frozen=True)
class CloudConfig:
    transport: TransportName
    host: str
    port: int
    token: str | None
    allow_anon: bool
    stateless: bool
    json_response: bool
    mcp_path: str = "/mcp"

    @property
    def require_token(self) -> bool:
        return self.transport == "streamable-http" and not self.allow_anon


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_transport(raw: str | None = None) -> TransportName:
    """Map CLI/env aliases onto FastMCP transport names."""
    value = (raw if raw is not None else _env("SPOTIFY_RIP_MCP_TRANSPORT")).strip().lower()
    if value in _STDIO_ALIASES:
        return "stdio"
    if value in _HTTP_ALIASES:
        return "streamable-http"
    raise ValueError(
        f"unknown MCP transport {raw!r}; use stdio or streamable-http"
    )


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_config(argv: Sequence[str] | None = None) -> CloudConfig:
    parser = argparse.ArgumentParser(prog="spotify-rip-mcp", add_help=True)
    parser.add_argument(
        "--transport",
        default=None,
        help="stdio (default) or streamable-http / http / cloud",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token. Env: SPOTIFY_RIP_MCP_TOKEN. Required for HTTP unless --allow-anon.",
    )
    parser.add_argument(
        "--allow-anon",
        action="store_true",
        default=None,
        help="Bind HTTP without a bearer token (local/dev only).",
    )
    parser.add_argument("--stateless", action="store_true", default=None)
    parser.add_argument("--json-response", action="store_true", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    transport = resolve_transport(args.transport)

    default_host = "0.0.0.0" if transport == "streamable-http" else "127.0.0.1"
    host = args.host or _env("SPOTIFY_RIP_MCP_HOST") or _env("FASTMCP_HOST") or default_host

    port_raw = args.port
    if port_raw is None:
        env_port = _env("SPOTIFY_RIP_MCP_PORT") or _env("PORT") or _env("FASTMCP_PORT") or "8000"
        port_raw = int(env_port)

    token = args.token if args.token is not None else (_env("SPOTIFY_RIP_MCP_TOKEN") or None)
    if token == "":
        token = None

    allow_anon = (
        True
        if args.allow_anon
        else _truthy(_env("SPOTIFY_RIP_MCP_ALLOW_ANON"))
    )
    stateless = (
        True
        if args.stateless
        else (
            _truthy(_env("SPOTIFY_RIP_MCP_STATELESS"))
            if _env("SPOTIFY_RIP_MCP_STATELESS")
            else transport == "streamable-http"
        )
    )
    json_response = (
        True
        if args.json_response
        else _truthy(_env("SPOTIFY_RIP_MCP_JSON"))
    )

    return CloudConfig(
        transport=transport,
        host=host,
        port=int(port_raw),
        token=token,
        allow_anon=allow_anon,
        stateless=stateless,
        json_response=json_response,
    )


def bearer_ok(authorization: str | None, token: str) -> bool:
    if not authorization or not token:
        return False
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    got = parts[1].encode("utf-8")
    exp = token.encode("utf-8")
    if len(got) != len(exp):
        return False
    return hmac.compare_digest(got, exp)


class BearerGate:
    """Reject unauthenticated MCP HTTP requests. ``/health`` stays public."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path in {"/health", "/healthz"}:
            await self.app(scope, receive, send)
            return
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers") or []
        }
        if bearer_ok(headers.get("authorization"), self.token):
            await self.app(scope, receive, send)
            return

        response = JSONResponse({"error": "unauthorized"}, status_code=401)
        await response(scope, receive, send)


class BearerMiddleware(BaseHTTPMiddleware):
    """Same gate as BearerGate, installed on the FastMCP Starlette app so lifespan still runs."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in {"/health", "/healthz"}:
            return await call_next(request)
        if bearer_ok(request.headers.get("authorization"), self.token):
            return await call_next(request)
        return JSONResponse({"error": "unauthorized"}, status_code=401)


def _register_health(mcp: Any) -> None:
    if getattr(mcp, "_spotify_rip_health_registered", False):
        return

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True, "server": getattr(mcp, "name", "spotify-rip")})

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    mcp._spotify_rip_health_registered = True


def apply_http(mcp: Any, cfg: CloudConfig) -> None:
    """Mutate FastMCP settings so ``mcp.run(transport="streamable-http")`` binds publicly."""
    from mcp.server.transport_security import TransportSecuritySettings

    if cfg.require_token and not cfg.token:
        raise SystemExit(
            "HTTP MCP requires SPOTIFY_RIP_MCP_TOKEN (or --token). "
            "Pass --allow-anon only for local development."
        )

    mcp.settings.host = cfg.host
    mcp.settings.port = cfg.port
    mcp.settings.stateless_http = cfg.stateless
    mcp.settings.json_response = cfg.json_response
    mcp.settings.streamable_http_path = cfg.mcp_path
    # Cursor's proxy sends a non-localhost Host header. Bearer auth is the gate.
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
    mcp._session_manager = None
    _register_health(mcp)

    if not cfg.token:
        return

    inner = mcp.streamable_http_app

    def wrapped_app() -> Any:
        app = inner()
        app.add_middleware(BearerMiddleware, token=cfg.token)
        return app

    mcp.streamable_http_app = wrapped_app  # type: ignore[method-assign]


def run(mcp: Any, cfg: CloudConfig) -> None:
    if cfg.transport == "stdio":
        mcp.run(transport="stdio")
        return
    apply_http(mcp, cfg)
    mcp.run(transport="streamable-http")
