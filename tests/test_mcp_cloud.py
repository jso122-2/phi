"""Cloud / Streamable HTTP transport for the MCP server."""
from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from mcp_server.cloud import (
    BearerGate,
    CloudConfig,
    apply_http,
    bearer_ok,
    resolve_config,
    resolve_transport,
)


def test_resolve_transport_aliases():
    assert resolve_transport("stdio") == "stdio"
    assert resolve_transport("") == "stdio"
    assert resolve_transport("http") == "streamable-http"
    assert resolve_transport("cloud") == "streamable-http"
    assert resolve_transport("streamable-http") == "streamable-http"
    with pytest.raises(ValueError):
        resolve_transport("sse")


def test_resolve_config_http_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SPOTIFY_RIP_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SPOTIFY_RIP_MCP_ALLOW_ANON", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    cfg = resolve_config(["--transport", "cloud", "--allow-anon", "--port", "9001"])
    assert cfg.transport == "streamable-http"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9001
    assert cfg.allow_anon is True
    assert cfg.stateless is True


def test_resolve_config_env_token_and_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPOTIFY_RIP_MCP_TRANSPORT", "http")
    monkeypatch.setenv("SPOTIFY_RIP_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("PORT", "8088")
    cfg = resolve_config([])
    assert cfg.transport == "streamable-http"
    assert cfg.token == "s3cret"
    assert cfg.port == 8088
    assert cfg.require_token is True


def test_bearer_ok_timing_safe():
    assert bearer_ok("Bearer abc", "abc") is True
    assert bearer_ok("bearer abc", "abc") is True
    assert bearer_ok("Bearer abcd", "abc") is False
    assert bearer_ok("Basic abc", "abc") is False
    assert bearer_ok(None, "abc") is False


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    await JSONResponse({"ok": True})(scope, receive, send)


def test_bearer_gate_health_is_public():
    app = BearerGate(_ok_app, "tok")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/mcp").status_code == 401
    assert client.get("/mcp", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert client.get("/mcp", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_apply_http_requires_token():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("t")
    cfg = CloudConfig(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        token=None,
        allow_anon=False,
        stateless=True,
        json_response=True,
    )
    with pytest.raises(SystemExit):
        apply_http(mcp, cfg)


def test_apply_http_streamable_initialize():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("cloud-test")

    @mcp.tool()
    def ping() -> str:
        return "pong"

    cfg = CloudConfig(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        token="tok",
        allow_anon=False,
        stateless=True,
        json_response=True,
    )
    apply_http(mcp, cfg)
    app = mcp.streamable_http_app()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        denied = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert denied.status_code == 401

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        }
        resp = client.post(
            "/mcp",
            json=payload,
            headers={
                "Authorization": "Bearer tok",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200, resp.text
        body = None
        if resp.headers.get("content-type", "").startswith("application/json"):
            body = resp.json()
        else:
            text = resp.text
            assert "jsonrpc" in text
            line = next(ln for ln in text.splitlines() if ln.startswith("data: "))
            body = json.loads(line[len("data: "):])
        assert body["result"]["serverInfo"]["name"] == "cloud-test"
        tools_hint = body["result"].get("capabilities", {}).get("tools")
        assert tools_hint is not None

        listed = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={
                "Authorization": "Bearer tok",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert listed.status_code == 200
        listed_body = listed.json() if listed.headers.get("content-type", "").startswith("application/json") else None
        if listed_body is None:
            line = next(ln for ln in listed.text.splitlines() if ln.startswith("data: "))
            listed_body = json.loads(line[len("data: "):])
        names = {t["name"] for t in listed_body["result"]["tools"]}
        assert "ping" in names


def test_uvicorn_binds_health_and_rejects_anon():
    """Process-level check: Streamable HTTP listens on a TCP port."""
    import socket
    import threading
    import time
    import urllib.error
    import urllib.request

    from mcp.server.fastmcp import FastMCP

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    mcp = FastMCP("cloud-bind")
    cfg = CloudConfig(
        transport="streamable-http",
        host="127.0.0.1",
        port=port,
        token="tok",
        allow_anon=False,
        stateless=True,
        json_response=True,
    )
    apply_http(mcp, cfg)

    thread = threading.Thread(target=lambda: mcp.run(transport="streamable-http"), daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/health"
    last_err: Exception | None = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(url, timeout=0.3) as resp:
                assert json.loads(resp.read())["ok"] is True
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            time.sleep(0.1)
    assert last_err is None, last_err

    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/mcp", timeout=1)
    assert caught.value.code == 401

