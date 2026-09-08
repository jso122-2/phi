"""
graph.notion_ingestion — Notion API client + vault sync pipeline.

Architecture
------------

  Notion (reservoir)   ─────────────────────────────────────────────────
                         Database pages, standalone pages, block content
                         Read via Notion REST API (token: NOTION_API_TOKEN)
                                │
                         NotionClient.fetch_all_pages()
                                │
                         notion_to_md()   block content → Obsidian markdown
                                │
  Obsidian (graph)     ─────────────────────────────────────────────────
                         vault/notion/<slug>.md
                         Ingested through IngestionPipeline → links + hub
                         Committed via graph_commit / manifest

Flow
----

  1. NotionClient fetches all databases and standalone pages accessible
     to the integration token.
  2. Each Notion page is converted to an IngestedDoc (Obsidian markdown
     with YAML front-matter preserved as metadata).
  3. The IngestionPipeline writes .md files under vault/notion/ and
     cross-links them semantically.
  4. An IngestionManifest is written; the MCP sync_notion tool reads it
     to pulse the harmonic index and update the vault graph.

Credentials
-----------
Set NOTION_API_TOKEN (Notion integration token).
Optionally set NOTION_ROOT_PAGE_ID or NOTION_DATABASE_ID to restrict scope.

Add the token in Cursor Dashboard → Cloud Agents → Secrets so it is
available in all cloud agent runs.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from graph.node import VAULT_ROOT
from graph.ingestion import IngestedDoc, IngestionPipeline, IngestionManifest

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOTION_API_BASE  = "https://api.notion.com/v1"
NOTION_VERSION   = "2022-06-28"
_NOTION_OUT_DIR  = VAULT_ROOT / "notion"          # vault output dir
_MANIFEST_FILE   = _NOTION_OUT_DIR / "notion-ingest-manifest.json"
_DEFAULT_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Notion API client (stdlib-only, no external deps)
# ---------------------------------------------------------------------------

class NotionAuthError(Exception):
    """Missing or invalid NOTION_API_TOKEN."""


class NotionAPIError(Exception):
    """Non-200 response from the Notion API."""
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body   = body
        super().__init__(f"Notion API {status}: {body[:200]}")


class NotionClient:
    """
    Minimal Notion REST API client using the standard library only.

    Reads the integration token from ``NOTION_API_TOKEN`` (env var).
    All methods paginate automatically and return full result lists.

    Parameters
    ----------
    token      Override env var (useful in tests).
    timeout    HTTP request timeout in seconds.
    """

    def __init__(
        self,
        token:   Optional[str] = None,
        timeout: int           = _DEFAULT_TIMEOUT,
    ) -> None:
        self._token   = token or os.environ.get("NOTION_API_TOKEN", "")
        self._timeout = timeout
        if not self._token:
            raise NotionAuthError(
                "NOTION_API_TOKEN is not set. "
                "Add it in Cursor Dashboard → Cloud Agents → Secrets."
            )

    # ── low-level request ─────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path:   str,
        body:   dict | None = None,
    ) -> dict:
        url  = f"{NOTION_API_BASE}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body else None
        req  = Request(
            url,
            data   = data,
            method = method,
            headers = {
                "Authorization":  f"Bearer {self._token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type":   "application/json",
            },
        )
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except HTTPError as exc:
            raise NotionAPIError(exc.code, exc.read().decode(errors="replace")) from exc
        except URLError as exc:
            raise NotionAPIError(0, str(exc)) from exc

    # ── paginator ─────────────────────────────────────────────────────────

    def _paginate(
        self,
        method:   str,
        path:     str,
        body:     dict | None = None,
        page_size: int = 100,
    ) -> Iterator[dict]:
        """Yield all results from a paginated Notion endpoint."""
        cursor: str | None = None
        while True:
            payload: dict = dict(body or {})
            payload["page_size"] = page_size
            if cursor:
                payload["start_cursor"] = cursor
            resp = self._request(method, path, payload if method == "POST" else None)
            if method == "GET" and cursor:
                resp = self._request("GET", f"{path}?start_cursor={cursor}&page_size={page_size}")
            for item in resp.get("results", []):
                yield item
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

    # ── public API ────────────────────────────────────────────────────────

    def search_pages(self, query: str = "", filter_type: str = "page") -> list[dict]:
        """Search for pages (or databases) accessible to the integration."""
        body: dict = {
            "filter": {"property": "object", "value": filter_type},
        }
        if query:
            body["query"] = query
        return list(self._paginate("POST", "search", body))

    def search_databases(self) -> list[dict]:
        """Return all databases accessible to the integration."""
        return list(self._paginate("POST", "search", {
            "filter": {"property": "object", "value": "database"},
        }))

    def get_database_pages(self, database_id: str) -> list[dict]:
        """Query all pages in a database."""
        return list(self._paginate("POST", f"databases/{database_id}/query"))

    def get_block_children(self, block_id: str) -> list[dict]:
        """Fetch all child blocks of a page or block (paginated)."""
        return list(self._paginate("GET", f"blocks/{block_id}/children"))

    def get_page(self, page_id: str) -> dict:
        """Fetch a single page's metadata."""
        return self._request("GET", f"pages/{page_id}")


# ---------------------------------------------------------------------------
# Notion → Markdown converter
# ---------------------------------------------------------------------------

def _rich_text_to_str(rich_texts: list[dict]) -> str:
    """
    Concatenate Notion rich_text array into markdown text.

    Handles inline equations (type: "equation") as $...$ spans so that
    Obsidian renders them correctly via MathJax.
    """
    parts: list[str] = []
    for rt in rich_texts:
        if rt.get("type") == "equation":
            expr = rt.get("equation", {}).get("expression", "")
            parts.append(f"${expr}$")
        else:
            parts.append(rt.get("plain_text", ""))
    return "".join(parts)


def _page_title(page: dict) -> str:
    """Extract the title string from a Notion page object."""
    props = page.get("properties", {})
    for key in ("title", "Title", "Name", "name"):
        prop = props.get(key)
        if prop and prop.get("type") == "title":
            return _rich_text_to_str(prop.get("title", []))
    # Fall back to the first title-type property
    for prop in props.values():
        if prop.get("type") == "title":
            return _rich_text_to_str(prop.get("title", []))
    return page.get("id", "untitled")


def _blocks_to_md(blocks: list[dict], depth: int = 0) -> str:
    """Convert a flat list of Notion blocks to Obsidian markdown."""
    indent = "    " * depth
    lines: list[str] = []

    for block in blocks:
        btype = block.get("type", "")
        data  = block.get(btype, {})

        if btype == "paragraph":
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}{text}" if text else "")

        elif btype in ("heading_1", "heading_2", "heading_3"):
            level = int(btype[-1])
            text  = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"\n{'#' * level} {text}\n")

        elif btype == "bulleted_list_item":
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}- {text}")

        elif btype == "numbered_list_item":
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}1. {text}")

        elif btype == "to_do":
            checked = data.get("checked", False)
            text    = _rich_text_to_str(data.get("rich_text", []))
            box     = "[x]" if checked else "[ ]"
            lines.append(f"{indent}- {box} {text}")

        elif btype == "toggle":
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}> **{text}**")

        elif btype == "quote":
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}> {text}")

        elif btype == "code":
            lang  = data.get("language", "")
            text  = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"```{lang}\n{text}\n```")

        elif btype == "divider":
            lines.append("\n---\n")

        elif btype == "callout":
            icon = data.get("icon", {}).get("emoji", "")
            text = _rich_text_to_str(data.get("rich_text", []))
            lines.append(f"{indent}> {icon} {text}")

        elif btype == "equation":
            # Notion block-level LaTeX equation → Obsidian block math
            expr = data.get("expression", "")
            lines.append(f"\n$$\n{expr}\n$$\n")

        elif btype == "image":
            url_info = data.get("file") or data.get("external") or {}
            url  = url_info.get("url", "")
            cap  = _rich_text_to_str(data.get("caption", []))
            lines.append(f"![{cap}]({url})")

        elif btype == "bookmark":
            url  = data.get("url", "")
            cap  = _rich_text_to_str(data.get("caption", []))
            lines.append(f"[{cap or url}]({url})")

        elif btype == "child_page":
            title = data.get("title", "")
            lines.append(f"→ [[{title}]]")

        elif btype == "child_database":
            title = data.get("title", "")
            lines.append(f"→ [[{title}]]")

        else:
            # Unknown block type — include as comment
            lines.append(f"<!-- notion:{btype} -->")

    return "\n".join(lines)


def notion_to_md(page: dict, blocks: list[dict]) -> str:
    """
    Convert a Notion page + its blocks into Obsidian-style markdown.

    Returns the full .md text including YAML front-matter.
    """
    page_id  = page.get("id", "")
    title    = _page_title(page)
    created  = page.get("created_time", "")
    edited   = page.get("last_edited_time", "")
    url      = page.get("url", "")

    front = (
        f"---\n"
        f"notion_id: {page_id}\n"
        f"notion_url: {url}\n"
        f"created: {created}\n"
        f"edited: {edited}\n"
        f"source: notion\n"
        f"tags: [notion, imported]\n"
        f"---\n\n"
    )
    body = _blocks_to_md(blocks)
    return f"{front}# {title}\n\n{body}\n"


# ---------------------------------------------------------------------------
# Page → IngestedDoc conversion
# ---------------------------------------------------------------------------

def _page_to_doc(page: dict, blocks: list[dict]) -> IngestedDoc:
    title = _page_title(page)
    text  = notion_to_md(page, blocks)
    return IngestedDoc(
        title    = title,
        text     = text,
        tags     = ["notion", "imported"],
        metadata = {
            "notion_id":  page.get("id", ""),
            "notion_url": page.get("url", ""),
            "created":    page.get("created_time", ""),
            "edited":     page.get("last_edited_time", ""),
            "source":     "notion",
        },
    )


# ---------------------------------------------------------------------------
# NotionSyncer
# ---------------------------------------------------------------------------

@dataclass
class SyncResult:
    """Result of a full Notion→Obsidian sync run."""
    n_pages:     int
    n_databases: int
    n_written:   int
    n_skipped:   int
    manifest:    Optional[IngestionManifest]
    errors:      list[str]
    elapsed_s:   float
    timestamp:   str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def summary(self) -> str:
        lines = [
            f"NotionSync  pages={self.n_pages}  dbs={self.n_databases}"
            f"  written={self.n_written}  skipped={self.n_skipped}"
            f"  errors={len(self.errors)}  elapsed={self.elapsed_s:.1f}s",
        ]
        if self.errors:
            for e in self.errors[:5]:
                lines.append(f"  ✗ {e}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "n_pages":     self.n_pages,
            "n_databases": self.n_databases,
            "n_written":   self.n_written,
            "n_skipped":   self.n_skipped,
            "errors":      self.errors,
            "elapsed_s":   round(self.elapsed_s, 2),
            "timestamp":   self.timestamp,
            "manifest":    (
                {
                    "n_written": self.manifest.n_written,
                    "hub_counts": self.manifest.hub_counts,
                }
                if self.manifest else None
            ),
        }


class NotionSyncer:
    """
    Orchestrates the Notion → Obsidian vault sync.

    1. Fetches all pages and database pages from Notion.
    2. Downloads block content for each page.
    3. Converts to IngestedDoc and runs the IngestionPipeline.
    4. Writes results under ``<vault>/notion/``.
    5. Returns a SyncResult for MCP consumption.

    Parameters
    ----------
    token           Notion API token (defaults to NOTION_API_TOKEN env var).
    output_dir      Vault directory to write .md files to.
    max_pages       Safety cap on total pages fetched (0 = unlimited).
    fetch_timeout   HTTP timeout per request.
    """

    def __init__(
        self,
        token:         Optional[str]  = None,
        output_dir:    Optional[Path] = None,
        max_pages:     int            = 0,
        fetch_timeout: int            = _DEFAULT_TIMEOUT,
    ) -> None:
        self._client     = NotionClient(token=token, timeout=fetch_timeout)
        self._output_dir = output_dir or _NOTION_OUT_DIR
        self._max_pages  = max_pages

    def sync(self) -> SyncResult:
        """Run the full sync and return a SyncResult."""
        t0     = time.monotonic()
        errors: list[str] = []
        docs:   list[IngestedDoc] = []
        n_pages = 0
        n_dbs   = 0

        # ── 1. Standalone pages ─────────────────────────────────────────────
        try:
            pages = self._client.search_pages()
            for page in pages:
                if self._max_pages and n_pages >= self._max_pages:
                    break
                try:
                    blocks = self._client.get_block_children(page["id"])
                    docs.append(_page_to_doc(page, blocks))
                    n_pages += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"page {page.get('id', '?')}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"search_pages failed: {exc}")

        # ── 2. Database pages ───────────────────────────────────────────────
        try:
            databases = self._client.search_databases()
            for db in databases:
                db_id = db.get("id", "")
                n_dbs += 1
                try:
                    db_pages = self._client.get_database_pages(db_id)
                    for page in db_pages:
                        if self._max_pages and n_pages >= self._max_pages:
                            break
                        try:
                            blocks = self._client.get_block_children(page["id"])
                            docs.append(_page_to_doc(page, blocks))
                            n_pages += 1
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"db-page {page.get('id', '?')}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"database {db_id}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"search_databases failed: {exc}")

        # ── 3. Ingest into Obsidian ─────────────────────────────────────────
        manifest: Optional[IngestionManifest] = None
        if docs:
            try:
                self._output_dir.mkdir(parents=True, exist_ok=True)
                pipeline = IngestionPipeline(output_dir=self._output_dir)
                manifest = pipeline.run(docs)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ingestion pipeline: {exc}")

        elapsed = time.monotonic() - t0
        result  = SyncResult(
            n_pages     = n_pages,
            n_databases = n_dbs,
            n_written   = manifest.n_written if manifest else 0,
            n_skipped   = manifest.n_skipped if manifest else 0,
            manifest    = manifest,
            errors      = errors,
            elapsed_s   = round(elapsed, 2),
        )
        _log.info(result.summary())
        return result


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def run_notion_sync(
    token:         Optional[str]  = None,
    output_dir:    Optional[Path] = None,
    max_pages:     int            = 0,
    fetch_timeout: int            = _DEFAULT_TIMEOUT,
) -> SyncResult:
    """
    Run a full Notion→Obsidian sync and return the result.

    Raises NotionAuthError if NOTION_API_TOKEN is not set.
    All other errors are collected into SyncResult.errors rather than raised,
    so a partial sync is still usable.
    """
    syncer = NotionSyncer(
        token         = token,
        output_dir    = output_dir,
        max_pages     = max_pages,
        fetch_timeout = fetch_timeout,
    )
    return syncer.sync()
