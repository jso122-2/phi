"""
Oesophagus — ingestion pipeline for the Obsidian vault graph.

Architecture: the tube that feeds the vault (stomach).

                 ┌─────────────┐
   source        │   Scanner   │  discovers .txt, audio, video files
   directory ──► │             │
                 └──────┬──────┘
                        │ file paths
                 ┌──────▼──────┐
                 │  Sentinel   │  blocks / redacts sensitive content
                 │   Gate      │  hard-blocks before any content is parsed
                 └──────┬──────┘
                        │ cleared files
                 ┌──────▼──────┐
                 │  Transform  │  .txt → VaultNode skeleton
                 │  Workers    │  audio/video → metadata stub
                 └──────┬──────┘
                        │ IngestionItem list
                 ┌──────▼──────┐
                 │  Cerberus   │  bind-guards each transform worker
                 │   Guard     │  respawns failing workers mathematically
                 └──────┬──────┘
                        │ passed items
                 ┌──────▼──────┐
                 │   Vault     │  writes .md nodes into sessions/ingest/
                 │   Writer    │
                 └─────────────┘

No Pericles watchdog is used in this pipeline.
The only quality gate is the Cerberus bind (ceb_1, ceb_2).

Supported ingest formats
------------------------
Text:
  .txt — primary ingest format; full content read and vaulted

Audio (metadata stub — no rip yet, rip layer comes later):
  .mp3, .flac, .wav, .aac, .ogg, .m4a, .opus

Video (metadata stub — no rip yet):
  .mp4, .mkv, .avi, .mov, .webm, .m4v

Blocked by Sentinel (never reach the vault):
  See workers.sentinel for the full block-list.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Iterator

from workers.cerberus import CerberusExhausted, CerberusGuard, BindResult, evaluate
from workers.sentinel import SentinelReport, screen


# ---------------------------------------------------------------------------
# File-type classification
# ---------------------------------------------------------------------------


class FileKind(Enum):
    TEXT = auto()
    AUDIO = auto()
    VIDEO = auto()
    UNKNOWN = auto()


_AUDIO_EXTS: frozenset[str] = frozenset({
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".alac",
})
_VIDEO_EXTS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv",
})


def classify(path: Path) -> FileKind:
    ext = path.suffix.lower()
    if ext == ".txt":
        return FileKind.TEXT
    if ext in _AUDIO_EXTS:
        return FileKind.AUDIO
    if ext in _VIDEO_EXTS:
        return FileKind.VIDEO
    return FileKind.UNKNOWN


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan_directory(
    source: Path,
    *,
    recurse: bool = True,
    max_files: int = 10_000,
) -> list[Path]:
    """
    Discover ingest-eligible files under `source`.

    Returns .txt, audio, and video files only — .md files are vault nodes
    and are never re-ingested by the oesophagus.
    """
    eligible_exts = {".txt"} | _AUDIO_EXTS | _VIDEO_EXTS

    found: list[Path] = []
    glob_fn = source.rglob if recurse else source.glob
    for p in sorted(glob_fn("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in eligible_exts:
            found.append(p)
        if len(found) >= max_files:
            break
    return found


# ---------------------------------------------------------------------------
# Ingestion item (result of transform stage)
# ---------------------------------------------------------------------------


@dataclass
class IngestionItem:
    source_path: str
    kind: FileKind
    title: str
    body: str                    # vault-ready markdown body
    tags: list[str]
    sentinel: SentinelReport
    transform_metric: float      # metric passed to Cerberus (0–1 quality signal)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.sentinel.allowed


# ---------------------------------------------------------------------------
# Transform workers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str, maxlen: int = 40) -> str:
    return _SLUG_RE.sub("-", text.lower()[:maxlen]).strip("-")


def _transform_txt(path: Path, report: SentinelReport) -> IngestionItem:
    """
    Transform a .txt file into an IngestionItem.

    Quality metric: ratio of non-whitespace characters to total characters.
    A file of pure whitespace scores 0.0; dense prose scores near 1.0.
    We target metric = 1.0 for the Cerberus gate (|x - 1| = 0 → passes).
    """
    text = report.safe_text or ""
    if not text and report.allowed:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return IngestionItem(
                source_path=str(path),
                kind=FileKind.TEXT,
                title=path.stem,
                body="",
                tags=["ingest", "txt", "error"],
                sentinel=report,
                transform_metric=0.0,
                error=str(exc),
            )

    stripped = text.strip()
    total = len(text)
    non_ws = sum(1 for c in text if not c.isspace())
    metric = (non_ws / total) if total > 0 else 0.0

    body = f"## Source\n\n`{path.name}`\n\n## Content\n\n{stripped}"
    if report.redacted:
        redaction_note = (
            "\n\n---\n\n> **Sentinel:** "
            + ", ".join(report.redactions)
            + " pattern(s) were redacted from this file."
        )
        body += redaction_note

    return IngestionItem(
        source_path=str(path),
        kind=FileKind.TEXT,
        title=path.stem,
        body=body,
        tags=["ingest", "txt"],
        sentinel=report,
        transform_metric=metric,
    )


def _transform_audio(path: Path, report: SentinelReport) -> IngestionItem:
    """
    Produce a metadata stub for an audio file.
    Full ripping is handled by a dedicated rip layer (not built yet).
    Metric is always 1.0 — stubs always pass Cerberus.
    """
    size_kb = round(path.stat().st_size / 1024, 1) if path.exists() else 0.0
    body = (
        f"## Audio file\n\n"
        f"- **File:** `{path.name}`\n"
        f"- **Format:** `{path.suffix.lstrip('.')}`\n"
        f"- **Size:** {size_kb} KB\n"
        f"- **Status:** metadata stub — rip pending\n\n"
        f"#audio #ingest #pending-rip"
    )
    return IngestionItem(
        source_path=str(path),
        kind=FileKind.AUDIO,
        title=path.stem,
        body=body,
        tags=["ingest", "audio", "pending-rip"],
        sentinel=report,
        transform_metric=1.0,
    )


def _transform_video(path: Path, report: SentinelReport) -> IngestionItem:
    """Metadata stub for a video file. Rip layer comes later."""
    size_mb = round(path.stat().st_size / 1_048_576, 2) if path.exists() else 0.0
    body = (
        f"## Video file\n\n"
        f"- **File:** `{path.name}`\n"
        f"- **Format:** `{path.suffix.lstrip('.')}`\n"
        f"- **Size:** {size_mb} MB\n"
        f"- **Status:** metadata stub — rip pending\n\n"
        f"#video #ingest #pending-rip"
    )
    return IngestionItem(
        source_path=str(path),
        kind=FileKind.VIDEO,
        title=path.stem,
        body=body,
        tags=["ingest", "video", "pending-rip"],
        sentinel=report,
        transform_metric=1.0,
    )


def _transform(path: Path, report: SentinelReport) -> IngestionItem:
    """Dispatch to the correct transform worker by file kind."""
    kind = classify(path)
    if kind == FileKind.TEXT:
        return _transform_txt(path, report)
    if kind == FileKind.AUDIO:
        return _transform_audio(path, report)
    if kind == FileKind.VIDEO:
        return _transform_video(path, report)
    return IngestionItem(
        source_path=str(path),
        kind=FileKind.UNKNOWN,
        title=path.stem,
        body="",
        tags=["ingest", "unknown"],
        sentinel=report,
        transform_metric=0.0,
        error=f"unsupported file type: {path.suffix}",
    )


# ---------------------------------------------------------------------------
# Vault writer
# ---------------------------------------------------------------------------

_INGEST_SUBDIR = "ingest"


def _vault_node_content(item: IngestionItem, ts: str) -> str:
    tag_line = " ".join(f"#{t}" for t in item.tags)
    return (
        f"# {item.title}\n\n"
        f"{tag_line}\n\n"
        f"**Ingested:** {ts}  \n"
        f"**Source:** `{item.source_path}`  \n"
        f"**Kind:** {item.kind.name.lower()}\n\n"
        f"---\n\n"
        f"{item.body}\n\n"
        f"---\n\n"
        f"→ [[sessions]] — session index  \n"
        f"→ [[graph]] — graph worker hub  \n"
        f"\n*Ingested by `workers/oesophagus.py`*\n"
    )


def write_vault_node(item: IngestionItem, vault_root: Path) -> Path:
    """Write an IngestionItem as a vault .md node. Returns the written path."""
    ingest_dir = vault_root / "sessions" / _INGEST_SUBDIR
    ingest_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    slug = _slug(item.title)
    filename = f"{ts}-{slug}.md"

    content = _vault_node_content(item, ts)
    out_path = ingest_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Ingestion result
# ---------------------------------------------------------------------------


@dataclass
class OesophagusResult:
    source_dir: str
    n_scanned: int = 0
    n_blocked: int = 0
    n_redacted: int = 0
    n_ingested: int = 0
    n_cerberus_respawned: int = 0
    n_failed: int = 0
    elapsed_s: float = 0.0
    items: list[IngestionItem] = field(default_factory=list)
    written_paths: list[str] = field(default_factory=list)
    bind_log: list[BindResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "source_dir": self.source_dir,
            "scanned": self.n_scanned,
            "blocked": self.n_blocked,
            "redacted": self.n_redacted,
            "ingested": self.n_ingested,
            "cerberus_respawned": self.n_cerberus_respawned,
            "failed": self.n_failed,
            "elapsed_s": round(self.elapsed_s, 3),
            "written": self.written_paths,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def ingest(
    source: Path,
    vault_root: Path,
    *,
    recurse: bool = True,
    max_files: int = 10_000,
    cerberus_tau_1: float = 0.5,
    cerberus_tau_2: float = 10.0,
    cerberus_max_retries: int = 4,
    dry_run: bool = False,
) -> OesophagusResult:
    """
    Run the full oesophagus ingestion pipeline.

    Parameters
    ----------
    source           : directory to scan for ingest-eligible files
    vault_root       : root of the Obsidian vault (Spotify-rip/)
    recurse          : whether to recurse into subdirectories
    max_files        : hard cap on files scanned per run
    cerberus_tau_1   : soft threshold for ceb_1
    cerberus_tau_2   : hard threshold for ceb_2
    cerberus_max_retries : max retries per file before marking failed
    dry_run          : if True, skip vault writes (scan + transform only)
    """
    t0 = time.perf_counter()
    result = OesophagusResult(source_dir=str(source))

    # ── Stage 1: Scan ────────────────────────────────────────────────────────
    paths = scan_directory(source, recurse=recurse, max_files=max_files)
    result.n_scanned = len(paths)

    for path in paths:
        # ── Stage 2: Sentinel gate ───────────────────────────────────────────
        report = screen(path)
        if not report.allowed:
            result.n_blocked += 1
            result.errors.append(f"BLOCKED {path.name}: {report.block_reason}")
            continue
        if report.redacted:
            result.n_redacted += 1

        # ── Stage 3 + 4: Transform + Cerberus guard ──────────────────────────
        retry_count = 0

        def _make_transform_fn(p: Path = path, r: SentinelReport = report):
            def _fn():
                return _transform(p, r)
            return _fn

        item: IngestionItem | None = None
        last_bind: BindResult | None = None

        while retry_count <= cerberus_max_retries:
            item = _transform(path, report)
            bind = evaluate(
                item.transform_metric,
                M=retry_count,
                tau_1=cerberus_tau_1,
                tau_2=cerberus_tau_2,
            )
            result.bind_log.append(bind)
            last_bind = bind

            if bind.passed:
                break

            if bind.hard_violation:
                result.n_cerberus_respawned += 1
                retry_count = 0
            else:
                retry_count += 1

            if retry_count > cerberus_max_retries:
                item.error = f"Cerberus exhausted after {cerberus_max_retries} retries. Last bind: {bind}"
                break

        if item is None or item.error:
            result.n_failed += 1
            if item:
                result.errors.append(f"FAILED {path.name}: {item.error}")
            result.items.append(item or IngestionItem(
                source_path=str(path),
                kind=classify(path),
                title=path.stem,
                body="",
                tags=["ingest", "failed"],
                sentinel=report,
                transform_metric=0.0,
                error="transform produced None",
            ))
            continue

        result.items.append(item)

        # ── Stage 5: Vault write ─────────────────────────────────────────────
        if not dry_run:
            try:
                written = write_vault_node(item, vault_root)
                result.written_paths.append(str(written))
                result.n_ingested += 1
            except OSError as exc:
                result.n_failed += 1
                result.errors.append(f"WRITE_ERROR {path.name}: {exc}")
        else:
            result.n_ingested += 1

    result.elapsed_s = round(time.perf_counter() - t0, 6)
    return result


# ---------------------------------------------------------------------------
# Convenience: iterate ingest results as they complete (generator form)
# ---------------------------------------------------------------------------


def ingest_stream(
    source: Path,
    vault_root: Path,
    **kwargs,
) -> Iterator[IngestionItem]:
    """
    Generator form of ingest — yields each IngestionItem as it is processed.

    Useful for large directories where you want to start seeing results before
    the full pipeline completes.
    """
    paths = scan_directory(source, recurse=kwargs.get("recurse", True))
    for path in paths:
        report = screen(path)
        if not report.allowed:
            continue
        item = _transform(path, report)
        yield item
