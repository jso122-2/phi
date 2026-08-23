"""
TxtExtractor — ingest plain-text files into the unified graph.

Handles three common patterns found in the vault:
  1. Structured key-value  →  lines of the form  "key: value"
                              extracted as tags for edge connectivity
  2. Hash/state files      →  lines of hex or base64 content
                              content-fingerprinted; hash prefix stored as tag
  3. Plain prose / logs    →  treated as prose notes (kind="document")

One SymbolNode per file.  Empty files are skipped.

Design notes:
  - .txt files in the Obsidian vault often carry CAIRRN hub state, agent
    conversation hashes, and session logs — all high-signal for the graph.
  - Language tag "text" lets the BERT encoder recognise these as plain prose.
  - body_snippet truncated at 800 chars to stay within BERT max_length budget.
"""
import hashlib
import os
import re
from typing import List, Optional

from phi.data.symbol_node import SymbolNode

_KV_RE = re.compile(r"^([\w\-./]+)\s*[:=]\s*(.+)$")
_HASH_RE = re.compile(r"^[0-9a-fA-F]{16,}$")
_TAG_RE = re.compile(r"#([\w/-]+)")
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


class TxtExtractor:
    """Extract one SymbolNode per .txt file."""

    def extract(self, path: str, repo: Optional[str] = None) -> List[SymbolNode]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            return []

        raw = raw.strip()
        if not raw:
            return []

        mtime = os.path.getmtime(path)
        stem = os.path.basename(path).replace(".txt", "")
        name = stem.replace("-", " ").replace("_", " ").title()

        lines = raw.splitlines()
        tags: List[str] = []
        kv_pairs: List[str] = []
        hash_tags: List[str] = []
        subheadings: List[str] = []

        for line in lines[:200]:
            line = line.strip()
            if not line:
                continue

            # Inline #tags
            tags.extend(_TAG_RE.findall(line))

            # Markdown-style headings inside .txt
            m = _HEADING_RE.match(line)
            if m:
                subheadings.append(m.group(1).strip()[:60])
                continue

            # Structured key-value lines
            kv_m = _KV_RE.match(line)
            if kv_m:
                key = kv_m.group(1).lower()
                val = kv_m.group(2).strip()[:80]
                kv_pairs.append(f"{key}: {val}")
                tags.append(key)
                continue

            # Hash-content lines (CAIRRN state, etc.)
            if _HASH_RE.match(line):
                hash_tags.append(f"hash:{line[:8]}")

        # Dedupe tags; add hash fingerprints
        seen = set()
        clean_tags = []
        for t in tags + hash_tags:
            t = t.lower()
            if t not in seen:
                seen.add(t)
                clean_tags.append(t)

        # Content fingerprint as a stable tag
        content_hash = hashlib.sha1(raw.encode()).hexdigest()[:12]
        clean_tags.append(f"sha1:{content_hash}")

        # Detect file kind from name patterns
        kind = "document"
        if any(k in stem.lower() for k in ("hash", "cache", "state", "index")):
            kind = "hash_doc"
        elif any(k in stem.lower() for k in ("log", "session", "agent", "trace")):
            kind = "log"

        # Build body: prefer kv_pairs summary then raw prose
        if kv_pairs:
            docstring = " | ".join(kv_pairs[:6])
            body = "\n".join(kv_pairs[:20]) + "\n\n" + "\n".join(lines[:30])
        else:
            docstring = " ".join(lines[:3])[:200]
            body = "\n".join(lines[:50])

        return [SymbolNode(
            path=path,
            name=name,
            kind=kind,
            language="text",
            repo=repo,
            signature=f"txt: {name}",
            docstring=docstring[:300],
            body_snippet=body[:800],
            tags=clean_tags,
            subheadings=subheadings,
            modified_ts=mtime,
            created_ts=mtime,
        )]
