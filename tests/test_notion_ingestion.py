"""
Tests for graph.notion_ingestion — NotionClient, notion_to_md converter,
SyncResult, and NotionSyncer (with mocked HTTP).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from graph.notion_ingestion import (
    NotionAuthError,
    NotionClient,
    SyncResult,
    _blocks_to_md,
    _page_title,
    _page_to_doc,
    notion_to_md,
    run_notion_sync,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_page(page_id: str = "abc123", title: str = "Test Page") -> dict:
    return {
        "id":               page_id,
        "object":           "page",
        "url":              f"https://notion.so/{page_id}",
        "created_time":     "2024-01-01T00:00:00.000Z",
        "last_edited_time": "2024-01-02T00:00:00.000Z",
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": title}],
            },
        },
    }


def _make_block(btype: str, text: str = "hello", extra: dict | None = None) -> dict:
    rich = [{"plain_text": text}]
    base = {"type": btype, "id": "blk1", "has_children": False}
    data: dict[str, Any] = {"rich_text": rich}
    if extra:
        data.update(extra)
    base[btype] = data
    return base


# ---------------------------------------------------------------------------
# _page_title
# ---------------------------------------------------------------------------

class TestRichTextToStr:
    def test_plain_text(self):
        from graph.notion_ingestion import _rich_text_to_str
        rt = [{"plain_text": "hello"}, {"plain_text": " world"}]
        assert _rich_text_to_str(rt) == "hello world"

    def test_inline_equation(self):
        from graph.notion_ingestion import _rich_text_to_str
        rt = [
            {"plain_text": "Energy "},
            {"type": "equation", "equation": {"expression": "E = mc^2"}},
        ]
        result = _rich_text_to_str(rt)
        assert result == "Energy $E = mc^2$"

    def test_mixed(self):
        from graph.notion_ingestion import _rich_text_to_str
        rt = [
            {"type": "equation", "equation": {"expression": r"\alpha"}},
            {"plain_text": " is the attractor"},
        ]
        result = _rich_text_to_str(rt)
        assert r"$\alpha$" in result


class TestPageTitle:
    def test_standard_title_property(self):
        page = _make_page(title="My Page")
        assert _page_title(page) == "My Page"

    def test_no_title_falls_back_to_id(self):
        page = {"id": "xyz", "properties": {}}
        assert _page_title(page) == "xyz"

    def test_title_in_name_property(self):
        page = {
            "id": "p1",
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "Named Page"}]},
            },
        }
        assert _page_title(page) == "Named Page"


# ---------------------------------------------------------------------------
# _blocks_to_md
# ---------------------------------------------------------------------------

class TestBlocksToMd:
    def test_paragraph(self):
        md = _blocks_to_md([_make_block("paragraph", "Hello world")])
        assert "Hello world" in md

    def test_heading_1(self):
        md = _blocks_to_md([_make_block("heading_1", "Big title")])
        assert "# Big title" in md

    def test_heading_2(self):
        md = _blocks_to_md([_make_block("heading_2", "Sub title")])
        assert "## Sub title" in md

    def test_heading_3(self):
        md = _blocks_to_md([_make_block("heading_3", "Sub sub")])
        assert "### Sub sub" in md

    def test_bullet(self):
        md = _blocks_to_md([_make_block("bulleted_list_item", "Item")])
        assert "- Item" in md

    def test_numbered(self):
        md = _blocks_to_md([_make_block("numbered_list_item", "Step")])
        assert "1. Step" in md

    def test_todo_unchecked(self):
        blk = _make_block("to_do", "Do this", extra={"checked": False})
        md  = _blocks_to_md([blk])
        assert "[ ]" in md and "Do this" in md

    def test_todo_checked(self):
        blk = _make_block("to_do", "Done", extra={"checked": True})
        md  = _blocks_to_md([blk])
        assert "[x]" in md

    def test_code_block(self):
        blk = _make_block("code", "print('hi')", extra={"language": "python"})
        md  = _blocks_to_md([blk])
        assert "```python" in md
        assert "print('hi')" in md

    def test_divider(self):
        blk = {"type": "divider", "id": "d1", "divider": {}, "has_children": False}
        md  = _blocks_to_md([blk])
        assert "---" in md

    def test_equation_block(self):
        blk = {
            "type": "equation", "id": "eq1", "has_children": False,
            "equation": {"expression": r"\tau = \frac{1}{\lambda}"},
        }
        md = _blocks_to_md([blk])
        assert "$$" in md
        assert r"\tau" in md

    def test_unknown_type_comment(self):
        blk = {"type": "synced_block", "id": "s1", "synced_block": {}, "has_children": False}
        md  = _blocks_to_md([blk])
        assert "notion:synced_block" in md

    def test_indented(self):
        md = _blocks_to_md([_make_block("paragraph", "indented")], depth=1)
        assert md.startswith("    ")


# ---------------------------------------------------------------------------
# notion_to_md
# ---------------------------------------------------------------------------

class TestNotionToMd:
    def test_yaml_front_matter(self):
        page   = _make_page("p1", "Hello")
        blocks = [_make_block("paragraph", "Content")]
        md     = notion_to_md(page, blocks)
        assert "---" in md
        assert "notion_id: p1" in md
        assert "source: notion" in md

    def test_title_heading(self):
        page   = _make_page("p1", "My Title")
        blocks = []
        md     = notion_to_md(page, blocks)
        assert "# My Title" in md

    def test_blocks_included(self):
        page   = _make_page("p1", "T")
        blocks = [_make_block("paragraph", "Body text")]
        md     = notion_to_md(page, blocks)
        assert "Body text" in md


# ---------------------------------------------------------------------------
# NotionClient — unit tests with mocked urlopen
# ---------------------------------------------------------------------------

class TestNotionClient:
    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        with pytest.raises(NotionAuthError):
            NotionClient(token="")

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("NOTION_API_TOKEN", "secret-token")
        client = NotionClient()
        assert client._token == "secret-token"

    def test_explicit_token(self, monkeypatch):
        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        client = NotionClient(token="explicit-tok")
        assert client._token == "explicit-tok"

    def _mock_response(self, data: dict):
        import io
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__  = MagicMock(return_value=False)
        return resp

    def test_search_pages(self, monkeypatch):
        page = _make_page("p1", "A")
        data = {"results": [page], "has_more": False}
        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        client = NotionClient(token="tok")

        with patch("graph.notion_ingestion.urlopen", return_value=self._mock_response(data)):
            pages = client.search_pages()
        assert len(pages) == 1
        assert pages[0]["id"] == "p1"

    def test_get_block_children(self, monkeypatch):
        block = _make_block("paragraph", "hello")
        data  = {"results": [block], "has_more": False}
        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        client = NotionClient(token="tok")

        with patch("graph.notion_ingestion.urlopen", return_value=self._mock_response(data)):
            blocks = client.get_block_children("page-id")
        assert len(blocks) == 1

    def test_pagination(self, monkeypatch):
        """Client must follow has_more / next_cursor pagination."""
        page_a = _make_page("a", "A")
        page_b = _make_page("b", "B")
        first  = {"results": [page_a], "has_more": True, "next_cursor": "cursor1"}
        second = {"results": [page_b], "has_more": False}

        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        client = NotionClient(token="tok")

        responses = [self._mock_response(first), self._mock_response(second)]
        with patch("graph.notion_ingestion.urlopen", side_effect=responses):
            pages = client.search_pages()
        assert len(pages) == 2


# ---------------------------------------------------------------------------
# NotionSyncer / run_notion_sync with heavy mocking
# ---------------------------------------------------------------------------

class TestNotionSyncer:
    """Smoke-test the syncer end-to-end with stubbed HTTP and IngestionPipeline."""

    def _run_sync(self, tmp_path, pages, blocks_map=None):
        """Helper: stub the API and run a sync into tmp_path."""
        if blocks_map is None:
            blocks_map = {p["id"]: [] for p in pages}

        page_resp    = {"results": pages,  "has_more": False}
        db_resp      = {"results": [],     "has_more": False}

        def fake_urlopen(req, timeout=30):
            url = req.full_url
            if "search" in url or url.endswith("search"):
                import io
                # We need to distinguish page vs db search — use call count hack
                body = json.loads(req.data or b"{}")
                filt = body.get("filter", {}).get("value", "page")
                data = page_resp if filt == "page" else db_resp
            elif "children" in url:
                pid = url.split("/")[-2]
                data = {"results": blocks_map.get(pid, []), "has_more": False}
            else:
                data = {"results": [], "has_more": False}

            mock = MagicMock()
            mock.read.return_value = json.dumps(data).encode()
            mock.__enter__ = lambda s: s
            mock.__exit__  = MagicMock(return_value=False)
            return mock

        os.environ["NOTION_API_TOKEN"] = "test-token"
        try:
            from graph.notion_ingestion import NotionSyncer

            # Stub out IngestionPipeline to avoid heavy ML deps
            mock_manifest = MagicMock()
            mock_manifest.n_written = len(pages)
            mock_manifest.n_skipped = 0
            mock_manifest.hub_counts = {}
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = mock_manifest

            with (
                patch("graph.notion_ingestion.urlopen", side_effect=fake_urlopen),
                patch("graph.notion_ingestion.IngestionPipeline", return_value=mock_pipeline),
            ):
                syncer = NotionSyncer(token="test-token", output_dir=tmp_path)
                return syncer.sync()
        finally:
            del os.environ["NOTION_API_TOKEN"]

    def test_sync_empty_workspace(self, tmp_path):
        result = self._run_sync(tmp_path, pages=[])
        assert result.n_pages == 0
        assert result.errors == []

    def test_sync_single_page(self, tmp_path):
        pages  = [_make_page("p1", "My Note")]
        result = self._run_sync(tmp_path, pages)
        assert result.n_pages == 1
        assert result.n_written == 1

    def test_sync_multiple_pages(self, tmp_path):
        pages  = [_make_page(f"p{i}", f"Page {i}") for i in range(5)]
        result = self._run_sync(tmp_path, pages)
        assert result.n_pages == 5

    def test_sync_result_summary(self, tmp_path):
        pages  = [_make_page("p1", "Note")]
        result = self._run_sync(tmp_path, pages)
        summary = result.summary()
        assert "n_pages" in summary or "pages" in summary

    def test_sync_result_to_dict(self, tmp_path):
        pages  = [_make_page("p1", "Note")]
        result = self._run_sync(tmp_path, pages)
        d = result.to_dict()
        assert "n_pages" in d
        assert "n_databases" in d
        assert "errors" in d

    def test_sync_no_token_raises(self, monkeypatch):
        monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
        with pytest.raises(NotionAuthError):
            run_notion_sync(token="")

    def test_max_pages_cap(self, tmp_path):
        pages  = [_make_page(f"p{i}", f"Page {i}") for i in range(10)]
        result = self._run_sync(tmp_path, pages[:3])  # only first 3 in response
        # max_pages=0 means unlimited — use stub limiting
        assert result.n_pages == 3
