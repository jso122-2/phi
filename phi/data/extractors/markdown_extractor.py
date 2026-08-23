"""
Markdown extractor — refactored from ObsidianGraph._fetch_notes().

One SymbolNode per .md file. Preserves all NoteNode semantics:
  - title extracted from # heading or filename
  - wikilinks → outlinks
  - #tags → tags
  - timestamps from filename pattern or mtime
"""
import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from phi.data.symbol_node import SymbolNode

logger = logging.getLogger(__name__)

_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})-")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
_TAG_RE = re.compile(r"#([\w/-]+)")
_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


class MarkdownExtractor:
    """Extract one SymbolNode per .md file."""

    def extract(self, path: str, repo: Optional[str] = None) -> List[SymbolNode]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            return []

        title = self._extract_title(raw, path)
        created_ts, modified_ts = self._extract_timestamps(path, raw)

        # Inline #tags from body
        tags = _TAG_RE.findall(raw)

        # YAML frontmatter — extract tags, aliases, and any string values as tags
        fm_tags, fm_meta = self._extract_frontmatter(raw)
        tags = list(dict.fromkeys(tags + fm_tags))  # merge, dedupe

        outlinks = _WIKILINK_RE.findall(raw)
        body = self._extract_body(raw)[:1000]

        # H2/H3 subheadings as structural context
        subheadings = [m.group(2).strip()[:80] for m in _HEADING_RE.finditer(raw)][:12]

        return [SymbolNode(
            path=path,
            name=title,
            kind="note",
            language="markdown",
            repo=repo,
            signature=f"# {title}",
            docstring=body[:300],
            body_snippet=body[:800],
            outlinks=outlinks,
            tags=tags,
            subheadings=subheadings,
            created_ts=created_ts,
            modified_ts=modified_ts,
        )]

    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_frontmatter(content: str) -> Tuple[List[str], Dict[str, str]]:
        """
        Parse YAML frontmatter block (---...---) at start of file.
        Returns (tags_list, key_value_dict).
        Does a light parse — no full YAML library dependency.
        """
        m = _FRONTMATTER_RE.match(content)
        if not m:
            return [], {}

        tags: List[str] = []
        meta: Dict[str, str] = {}
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip().strip('"').strip("'")
                meta[key] = val
                # tags, aliases, category, type → use as graph tags
                if key in ("tags", "tag", "category", "type", "status", "aliases"):
                    # handle YAML list [a, b] or "a, b"
                    clean = val.strip("[]").replace('"', "").replace("'", "")
                    for t in re.split(r"[,\s]+", clean):
                        t = t.strip().lstrip("#")
                        if t:
                            tags.append(t.lower())
                elif val and len(val) < 50:
                    # Short string values as tags (e.g. "source: obsidian")
                    tags.append(f"{key}:{val.lower()}")
        return tags, meta

    @staticmethod
    def _extract_title(content: str, path: str) -> str:
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m:
            heading = m.group(1).strip()
            if not re.match(r"^[\d\s:TtZz.\-+/]+$", heading):
                return heading

        stem = os.path.basename(path).replace(".md", "")
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{6}-", "", stem).strip("-_ ")
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-t][\dtz.:\-+]+", "", stem, flags=re.IGNORECASE).strip("-_ ")
        if stem:
            return stem.replace("-", " ").title()

        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", ">", "-", "!", "```", "|")):
                return line[:60].rstrip()

        date_m = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
        return date_m.group(1) if date_m else os.path.basename(path).replace(".md", "")

    @staticmethod
    def _extract_body(content: str) -> str:
        body = re.sub(r"(^>.*\n)+", "", content, flags=re.MULTILINE)
        body = re.sub(r"^---+\s*\n", "", body, flags=re.MULTILINE)
        body = re.sub(r"^#\s+.+\n?", "", body, count=1, flags=re.MULTILINE)
        return body.strip()

    @staticmethod
    def _extract_timestamps(path: str, content: str) -> Tuple[float, float]:
        mtime = os.path.getmtime(path)
        fname = os.path.basename(path)
        m = _TS_RE.match(fname)
        if m:
            try:
                dt = datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6)),
                    tzinfo=timezone.utc,
                )
                created_ts = dt.timestamp()
            except ValueError:
                created_ts = mtime
        else:
            created_ts = mtime

        modified_ts = mtime
        for line in content.splitlines():
            if re.search(r"Edited:", line, re.IGNORECASE):
                m2 = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", line)
                if m2:
                    try:
                        modified_ts = datetime.strptime(
                            f"{m2.group(1)} {m2.group(2)}", "%Y-%m-%d %H:%M"
                        ).replace(tzinfo=timezone.utc).timestamp()
                    except ValueError:
                        pass
        return created_ts, modified_ts
