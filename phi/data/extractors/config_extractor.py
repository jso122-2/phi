"""
Config file extractor — YAML, JSON, TOML.

One SymbolNode per file. Only files inside a config/ or configs/ directory
are emitted; the gate will further filter based on connectivity + novelty.
"""
import os
import logging
from typing import List, Optional

from phi.data.symbol_node import SymbolNode

logger = logging.getLogger(__name__)

_CONFIG_DIRS = {"config", "configs", "configuration", "settings"}
_MAX_BODY = 600


class ConfigExtractor:
    """Extract a single SymbolNode per config file."""

    def extract(self, path: str, repo: Optional[str] = None) -> List[SymbolNode]:
        # Only emit if inside a recognised config directory
        parts = path.replace("\\", "/").split("/")
        if not any(p.lower() in _CONFIG_DIRS for p in parts):
            return []

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            return []

        suffix = os.path.splitext(path)[1].lower()
        lang = {".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml"}.get(suffix, "yaml")
        mtime = os.path.getmtime(path)
        name = os.path.basename(path)

        # Extract top-level comment lines as a docstring
        doc_lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith(("#", "//")):
                doc_lines.append(stripped.lstrip("#/ "))
            elif stripped:
                break
        doc = " ".join(doc_lines)[:300]

        return [SymbolNode(
            path=path,
            name=name,
            kind="config",
            language=lang,
            repo=repo,
            signature=f"{lang} config: {name}",
            docstring=doc,
            body_snippet=raw[:_MAX_BODY],
            modified_ts=mtime,
            created_ts=mtime,
        )]
