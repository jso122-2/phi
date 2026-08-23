"""
FilesystemCrawler — walk ~/  and dispatch to per-language extractors.

Produces a flat list of SymbolNode objects for UnifiedGraph.build().

Usage:
    crawler = FilesystemCrawler(cfg["crawler"])
    symbols = crawler.scan()                        # full scan
    new_syms = crawler.scan_incremental(since_ts)   # only changed files
"""
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from .symbol_node import SymbolNode
from .extractors import (
    PythonExtractor,
    JSExtractor,
    MarkdownExtractor,
    ConfigExtractor,
    TxtExtractor,
)

logger = logging.getLogger(__name__)

# ── Hard-coded exclusions (always skipped regardless of config) ───────────────
_HARD_EXCLUDE_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", ".pytest_cache",
    "build", "dist", ".cache", ".next", ".nuxt", ".svelte-kit",
    "Library", "Applications", ".Trash", "Movies", "Music", "Pictures",
    ".venv", "venv", "env", ".env", "site-packages",
    "eggs", ".eggs", "*.egg-info",
    ".tox", ".mypy_cache", ".ruff_cache",
    "coverage", ".coverage", "htmlcov",
    "Caches", "Logs", "Containers", "CoreSimulator",
}

_HARD_EXCLUDE_SUFFIXES: Set[str] = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv",
    ".ttf", ".otf", ".woff", ".woff2",
    ".db", ".sqlite", ".sqlite3",
    ".pt", ".pth", ".ckpt", ".bin",  # model weights
    ".lock",  # package lock files
}

_SUFFIX_TO_EXTRACTOR = {
    ".py":   "python",
    ".js":   "js",
    ".jsx":  "js",
    ".ts":   "js",
    ".tsx":  "js",
    ".mjs":  "js",
    ".cjs":  "js",
    ".md":   "markdown",
    ".txt":  "txt",      # plain-text notes, CAIRRN state, hash files
    ".yaml": "config",
    ".yml":  "config",
    ".json": "config",
    ".toml": "config",
}


class FilesystemCrawler:
    """
    Walk the filesystem and extract SymbolNodes from every supported file.

    Args:
        cfg: crawler config dict (from config.yaml["crawler"]).
             Recognised keys:
               roots                list of paths to scan (default: ["~/"])
               exclude_dirs         additional dir names to skip
               exclude_suffixes     additional file suffixes to skip
               max_file_size_bytes  files larger than this are skipped (default 500 KB)
               rescan_interval_seconds  used by CrawlerWatcher, not by crawl() itself
    """

    def __init__(self, cfg: Optional[dict] = None) -> None:
        cfg = cfg or {}
        raw_roots = cfg.get("roots", ["~/"])
        self.roots: List[str] = [str(Path(r).expanduser().resolve()) for r in raw_roots]
        self.max_bytes: int = cfg.get("max_file_size_bytes", 500_000)

        self._exclude_dirs: Set[str] = _HARD_EXCLUDE_DIRS | set(cfg.get("exclude_dirs", []))
        self._exclude_suffixes: Set[str] = _HARD_EXCLUDE_SUFFIXES | {
            s if s.startswith(".") else f".{s}"
            for s in cfg.get("exclude_suffixes", [])
        }

        self._py  = PythonExtractor()
        self._js  = JSExtractor()
        self._md  = MarkdownExtractor()
        self._cfg = ConfigExtractor()
        self._txt = TxtExtractor()

        # repo root cache: path → repo root (or None)
        self._repo_cache: Dict[str, Optional[str]] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def scan(self) -> List[SymbolNode]:
        """Full scan of all configured roots. Returns all SymbolNodes found."""
        start = time.time()
        symbols: List[SymbolNode] = []
        for root in self.roots:
            symbols.extend(self._walk(root))
        elapsed = time.time() - start
        logger.info(
            "Full scan complete: %d symbols from %d roots in %.1fs",
            len(symbols), len(self.roots), elapsed,
        )
        return symbols

    def scan_incremental(self, since_ts: float) -> List[SymbolNode]:
        """Return SymbolNodes from files modified after `since_ts` (epoch seconds)."""
        symbols: List[SymbolNode] = []
        for root in self.roots:
            symbols.extend(self._walk(root, since_ts=since_ts))
        logger.info("Incremental scan: %d new/modified symbols since %.0f", len(symbols), since_ts)
        return symbols

    # ──────────────────────────────────────────────────────────────────────────
    # Walk
    # ──────────────────────────────────────────────────────────────────────────

    def _walk(self, root: str, since_ts: Optional[float] = None) -> List[SymbolNode]:
        symbols: List[SymbolNode] = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # Prune excluded directories in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in self._exclude_dirs and not d.startswith(".")
            ]

            for fname in filenames:
                suffix = os.path.splitext(fname)[1].lower()
                if suffix in self._exclude_suffixes:
                    continue

                fpath = os.path.join(dirpath, fname)

                try:
                    stat = os.stat(fpath)
                except OSError:
                    continue

                if stat.st_size > self.max_bytes:
                    continue
                if since_ts is not None and stat.st_mtime <= since_ts:
                    continue

                extractor_key = _SUFFIX_TO_EXTRACTOR.get(suffix)
                if extractor_key is None:
                    continue

                repo = self._find_repo(dirpath)
                try:
                    syms = self._extract(fpath, extractor_key, repo)
                    symbols.extend(syms)
                except Exception as exc:
                    logger.debug("Extractor error on %s: %s", fpath, exc)

        return symbols

    def _extract(self, path: str, key: str, repo: Optional[str]) -> List[SymbolNode]:
        if key == "python":
            return self._py.extract(path, repo=repo)
        elif key == "js":
            return self._js.extract(path, repo=repo)
        elif key == "markdown":
            return self._md.extract(path, repo=repo)
        elif key == "config":
            return self._cfg.extract(path, repo=repo)
        elif key == "txt":
            return self._txt.extract(path, repo=repo)
        return []

    # ──────────────────────────────────────────────────────────────────────────
    # Repo detection
    # ──────────────────────────────────────────────────────────────────────────

    def _find_repo(self, dirpath: str) -> Optional[str]:
        """Walk up from dirpath to find the nearest .git directory."""
        if dirpath in self._repo_cache:
            return self._repo_cache[dirpath]

        current = dirpath
        while True:
            if os.path.isdir(os.path.join(current, ".git")):
                self._repo_cache[dirpath] = current
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        self._repo_cache[dirpath] = None
        return None
