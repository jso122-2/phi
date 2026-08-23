"""
Tests for workers.sentinel and workers.oesophagus.

All tests are filesystem-isolated using tmp_path (pytest fixture).
No vault writes touch the real Obsidian vault during testing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workers.sentinel import SentinelReport, screen, screen_batch
from workers.oesophagus import (
    FileKind,
    IngestionItem,
    OesophagusResult,
    classify,
    ingest,
    scan_directory,
    write_vault_node,
)


# ===========================================================================
# Sentinel
# ===========================================================================


class TestSentinelExtensionBlock:
    def test_pem_blocked(self, tmp_path):
        p = tmp_path / "secret.pem"
        p.write_text("-----BEGIN RSA PRIVATE KEY-----\nfoo\n")
        report = screen(p)
        assert not report.allowed
        assert "pem" in report.block_reason

    def test_env_blocked(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text("SECRET=abc123")
        report = screen(p)
        assert not report.allowed

    def test_txt_allowed(self, tmp_path):
        p = tmp_path / "notes.txt"
        p.write_text("Hello world")
        report = screen(p)
        assert report.allowed

    def test_md_allowed_by_extension(self, tmp_path):
        # .md files are not extension-blocked by sentinel (oesophagus scanner
        # excludes them at the scan stage, not the sentinel stage)
        p = tmp_path / "note.md"
        p.write_text("# Hello")
        report = screen(p)
        assert report.allowed


class TestSentinelPathQuarantine:
    def test_ssh_dir_blocked(self, tmp_path):
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        p = ssh_dir / "config.txt"
        p.write_text("Host example.com")
        report = screen(p)
        assert not report.allowed
        assert "quarantined directory" in report.block_reason

    def test_secrets_dir_blocked(self, tmp_path):
        d = tmp_path / "secrets"
        d.mkdir()
        p = d / "token.txt"
        p.write_text("my-token-here")
        report = screen(p)
        assert not report.allowed


class TestSentinelContentRedaction:
    def test_api_key_redacted(self, tmp_path):
        p = tmp_path / "config.txt"
        text = "api_key = supersecretvalue1234567890\nother: stuff"
        p.write_text(text)
        report = screen(p)
        assert report.allowed
        assert report.redacted
        assert "api_key" in report.redactions
        assert "supersecretvalue" not in (report.safe_text or "")

    def test_private_key_pem_in_content_redacted(self, tmp_path):
        p = tmp_path / "notes.txt"
        text = "Here is my key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAA\n"
        p.write_text(text)
        report = screen(p)
        assert report.allowed
        assert report.redacted

    def test_clean_file_not_redacted(self, tmp_path):
        p = tmp_path / "clean.txt"
        p.write_text("This is a perfectly normal text file about music.")
        report = screen(p)
        assert report.allowed
        assert not report.redacted

    def test_screen_with_text_argument(self, tmp_path):
        p = tmp_path / "inline.txt"
        p.write_text("dummy")
        report = screen(p, text="password = hunter2\nother stuff")
        assert report.redacted

    def test_screen_batch(self, tmp_path):
        (tmp_path / "a.txt").write_text("clean")
        (tmp_path / "b.pem").write_text("key data")
        reports = screen_batch([tmp_path / "a.txt", tmp_path / "b.pem"])
        assert reports[0].allowed
        assert not reports[1].allowed


# ===========================================================================
# Classify
# ===========================================================================


class TestClassify:
    @pytest.mark.parametrize("name,expected", [
        ("track.mp3", FileKind.AUDIO),
        ("movie.mkv", FileKind.VIDEO),
        ("notes.txt", FileKind.TEXT),
        ("archive.zip", FileKind.UNKNOWN),
        ("UPPER.MP3", FileKind.AUDIO),
    ])
    def test_kinds(self, tmp_path, name, expected):
        p = tmp_path / name
        assert classify(p) == expected


# ===========================================================================
# scan_directory
# ===========================================================================


class TestScanDirectory:
    def test_finds_txt(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.txt").write_text("world")
        paths = scan_directory(tmp_path)
        assert len(paths) == 2

    def test_skips_md(self, tmp_path):
        (tmp_path / "note.md").write_text("# note")
        (tmp_path / "data.txt").write_text("data")
        paths = scan_directory(tmp_path)
        assert all(p.suffix != ".md" for p in paths)

    def test_recurse_finds_nested(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")
        paths = scan_directory(tmp_path, recurse=True)
        assert any("nested" in p.name for p in paths)

    def test_no_recurse_skips_nested(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")
        (tmp_path / "top.txt").write_text("top")
        paths = scan_directory(tmp_path, recurse=False)
        assert len(paths) == 1
        assert paths[0].name == "top.txt"

    def test_max_files_cap(self, tmp_path):
        for i in range(10):
            (tmp_path / f"{i}.txt").write_text("x")
        paths = scan_directory(tmp_path, max_files=3)
        assert len(paths) == 3


# ===========================================================================
# ingest (dry_run=True — no vault writes)
# ===========================================================================


class TestIngest:
    def _source(self, tmp_path) -> Path:
        src = tmp_path / "source"
        src.mkdir()
        return src

    def _vault(self, tmp_path) -> Path:
        v = tmp_path / "vault"
        v.mkdir()
        return v

    def test_basic_txt_ingestion(self, tmp_path):
        src = self._source(tmp_path)
        (src / "notes.txt").write_text("Hello, this is a note about music.")
        result = ingest(src, self._vault(tmp_path), dry_run=True)
        assert result.n_scanned == 1
        assert result.n_ingested == 1
        assert result.n_blocked == 0

    def test_sensitive_file_blocked(self, tmp_path):
        # .pem files are not scan-eligible (oesophagus only scans .txt/audio/video)
        # so they never reach the sentinel. Block via a .txt inside a quarantined dir.
        src = self._source(tmp_path)
        secrets_dir = src / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "credentials.txt").write_text("token=abc")
        result = ingest(src, self._vault(tmp_path), dry_run=True)
        assert result.n_blocked == 1
        assert result.n_ingested == 0

    def test_redacted_file_still_ingested(self, tmp_path):
        src = self._source(tmp_path)
        (src / "config.txt").write_text("api_key = supersecrettoken1234567\nnormal content")
        result = ingest(src, self._vault(tmp_path), dry_run=True)
        assert result.n_redacted == 1
        assert result.n_ingested == 1

    def test_empty_source_dir(self, tmp_path):
        result = ingest(self._source(tmp_path), self._vault(tmp_path), dry_run=True)
        assert result.n_scanned == 0
        assert result.n_ingested == 0

    def test_mixed_content(self, tmp_path):
        # .pem files are not scan-eligible; blocked files use quarantined dirs.
        src = self._source(tmp_path)
        (src / "a.txt").write_text("clean text")
        secrets_dir = src / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "token.txt").write_text("credential data")
        (src / "c.txt").write_text("more text")
        result = ingest(src, self._vault(tmp_path), dry_run=True)
        assert result.n_scanned == 3        # a.txt, secrets/token.txt, c.txt
        assert result.n_blocked == 1        # secrets/token.txt
        assert result.n_ingested == 2       # a.txt, c.txt

    def test_result_summary_keys(self, tmp_path):
        result = ingest(self._source(tmp_path), self._vault(tmp_path), dry_run=True)
        s = result.summary()
        assert "scanned" in s
        assert "blocked" in s
        assert "ingested" in s
        assert "elapsed_s" in s

    def test_elapsed_recorded(self, tmp_path):
        result = ingest(self._source(tmp_path), self._vault(tmp_path), dry_run=True)
        assert result.elapsed_s >= 0.0


# ===========================================================================
# write_vault_node (real filesystem write)
# ===========================================================================


class TestWriteVaultNode:
    def _make_item(self, path: Path) -> IngestionItem:
        from workers.sentinel import screen
        report = screen(path, text="some content about music")
        from workers.oesophagus import _transform_txt
        return _transform_txt(path, report)

    def test_writes_md_file(self, tmp_path):
        src = tmp_path / "note.txt"
        src.write_text("This is a test note.")
        vault = tmp_path / "vault"
        vault.mkdir()
        item = self._make_item(src)
        written = write_vault_node(item, vault)
        assert written.exists()
        assert written.suffix == ".md"

    def test_written_content_contains_title(self, tmp_path):
        src = tmp_path / "my-track.txt"
        src.write_text("Content about a track.")
        vault = tmp_path / "vault"
        vault.mkdir()
        item = self._make_item(src)
        written = write_vault_node(item, vault)
        content = written.read_text()
        assert "my-track" in content

    def test_written_under_ingest_subdir(self, tmp_path):
        src = tmp_path / "x.txt"
        src.write_text("x")
        vault = tmp_path / "vault"
        vault.mkdir()
        item = self._make_item(src)
        written = write_vault_node(item, vault)
        assert "ingest" in str(written)
