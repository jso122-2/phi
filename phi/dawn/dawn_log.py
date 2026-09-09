"""
phi.dawn.dawn_log — DAWN project log writers.

Three write paths:

    log_bloom(bloom_id, data)
        Writes dawn/blooms/YYYY-MM-DD-{bloom_id}.md
        Overwrites any existing file for that bloom_id on the same day.

    log_tick(tick_data)
        Writes / appends to dawn/ticks/YYYY-MM-DD-daily.md
        Each call appends a new tick section to the daily file.

    log_tracer(tracer_id, state)
        Writes dawn/tracers/YYYY-MM-DD-{tracer_id}.md
        Overwrites any existing file for that tracer on the same day.

Each .md file uses YAML frontmatter:
    hub:       <hub from data, default HOME>
    layer:     dawn
    type:      bloom | tick | tracer
    timestamp: <ISO-8601 UTC>

The vault root is resolved as two directories above the phi/ package root
(i.e. /Users/jack0/Documents/phi by default, overridable via DAWN_VAULT env var).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Vault root resolution
# ---------------------------------------------------------------------------

def _vault_root() -> Path:
    """
    Return the vault root path.

    Precedence:
    1. DAWN_VAULT environment variable
    2. Two levels above the phi package (repo root)
    """
    env_root = os.environ.get("DAWN_VAULT", "")
    if env_root:
        return Path(env_root).resolve()
    # phi/dawn/dawn_log.py → phi/dawn → phi → repo root
    return Path(__file__).resolve().parents[2]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _iso_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Frontmatter builder
# ---------------------------------------------------------------------------

def _frontmatter(
    hub: str,
    log_type: str,
    timestamp: str,
    extra: dict[str, Any] | None = None,
) -> str:
    lines = [
        "---",
        f"hub: {hub}",
        "layer: dawn",
        f"type: {log_type}",
        f"timestamp: {timestamp}",
    ]
    if extra:
        for k, v in extra.items():
            # Render lists as YAML inline sequences
            if isinstance(v, list):
                items = ", ".join(str(i) for i in v)
                lines.append(f"{k}: [{items}]")
            elif isinstance(v, dict):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Body renderer — converts arbitrary dict to readable markdown
# ---------------------------------------------------------------------------

def _render_body(data: dict[str, Any], heading_prefix: str = "##") -> str:
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{heading_prefix} {k}")
            for sk, sv in v.items():
                lines.append(f"- **{sk}**: {sv}")
        elif isinstance(v, list):
            lines.append(f"**{k}**:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"**{k}**: {v}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# log_bloom
# ---------------------------------------------------------------------------

def log_bloom(bloom_id: str, data: dict[str, Any]) -> Path:
    """
    Write a bloom log to dawn/blooms/YYYY-MM-DD-{bloom_id}.md.

    bloom_id: unique identifier for this bloom event (e.g. "seed-7", "HOME-burst")
    data:     dict of bloom properties — hub, activation values, notes, etc.

    Returns the Path written.
    """
    now = _now_utc()
    hub = str(data.get("hub", "HOME"))
    timestamp = _iso_str(now)
    date = _date_str(now)

    vault = _vault_root()
    dest_dir = vault / "dawn" / "blooms"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{date}-{bloom_id}.md"

    # Extra frontmatter fields from data (excluding hub which is already in header)
    extra = {k: v for k, v in data.items() if k != "hub"}

    fm = _frontmatter(hub=hub, log_type="bloom", timestamp=timestamp, extra={"bloom_id": bloom_id})
    body = _render_body({k: v for k, v in data.items() if k not in ("hub",)})
    title = f"Bloom — {bloom_id}"

    content = f"{fm}\n\n# {title}\n\n{body}\n"
    dest.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# log_tick
# ---------------------------------------------------------------------------

def log_tick(tick_data: dict[str, Any]) -> Path:
    """
    Append a tick entry to dawn/ticks/YYYY-MM-DD-daily.md.

    tick_data: dict of tick properties — hub, tick_id, shard activations, etc.
               If a daily file already exists, the new tick is appended as a
               new section separated by a horizontal rule.

    Returns the Path written/appended to.
    """
    now = _now_utc()
    hub = str(tick_data.get("hub", "HOME"))
    timestamp = _iso_str(now)
    date = _date_str(now)

    vault = _vault_root()
    dest_dir = vault / "dawn" / "ticks"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{date}-daily.md"

    tick_body = _render_body({k: v for k, v in tick_data.items() if k != "hub"})

    if not dest.exists():
        # First tick of the day — write with frontmatter
        fm = _frontmatter(hub=hub, log_type="tick", timestamp=timestamp)
        content = f"{fm}\n\n# Daily Tick Log — {date}\n\n## Tick @ {timestamp}\n\n{tick_body}\n"
        dest.write_text(content, encoding="utf-8")
    else:
        # Subsequent ticks — append a new section
        append_block = f"\n---\n\n## Tick @ {timestamp}\n\n{tick_body}\n"
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(append_block)

    return dest


# ---------------------------------------------------------------------------
# log_tracer
# ---------------------------------------------------------------------------

def log_tracer(tracer_id: str, state: dict[str, Any]) -> Path:
    """
    Write a tracer state snapshot to dawn/tracers/YYYY-MM-DD-{tracer_id}.md.

    tracer_id: unique identifier for this tracer (e.g. "alpha", "thread-3")
    state:     dict of tracer state — hub, position, velocity, attractor, etc.

    Returns the Path written.
    """
    now = _now_utc()
    hub = str(state.get("hub", "HOME"))
    timestamp = _iso_str(now)
    date = _date_str(now)

    vault = _vault_root()
    dest_dir = vault / "dawn" / "tracers"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{date}-{tracer_id}.md"

    fm = _frontmatter(
        hub=hub,
        log_type="tracer",
        timestamp=timestamp,
        extra={"tracer_id": tracer_id},
    )
    body = _render_body({k: v for k, v in state.items() if k != "hub"})
    title = f"Tracer — {tracer_id}"

    content = f"{fm}\n\n# {title}\n\n{body}\n"
    dest.write_text(content, encoding="utf-8")
    return dest
