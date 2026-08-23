# -*- coding: utf-8 -*-
"""phi.meta._track_index — slug-based path index for the track store.

Provides the ``_Index`` class (thread-safe bi-directional path ↔ slug map)
plus the slug-generation helpers ``_slugify`` and ``_make_slug``.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_SLUG_RE  = re.compile(r"[^\w\-]")
_MAX_PART = 50


def _slugify(s: str) -> str:
    """Normalise *s* into a safe slug fragment. Returns '' for blank input."""
    s = s.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = _SLUG_RE.sub("", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:_MAX_PART]


def _make_slug(meta: dict, path: str) -> str:
    """Build a human-readable slug from track metadata, falling back to a path hash."""
    artist = _slugify(meta.get("artist") or "")
    title  = _slugify(meta.get("title")  or "")

    if artist and title:
        return f"{artist}__{title}"
    if title:
        return f"__{title}"
    if artist:
        return f"{artist}__"

    import hashlib
    h = hashlib.md5(path.encode()).hexdigest()[:8]
    return f"_unknown__{h}"


class _Index:
    """Thread-safe bi-directional index: path ↔ slug.

    Persisted to a JSON file; loaded eagerly on construction.
    """

    def __init__(self, index_file: Path) -> None:
        self._file = index_file
        self._lock = threading.Lock()
        self._path_to_slug: dict[str, str] = {}
        self._slug_to_path: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text())
            self._path_to_slug = data.get("path_to_slug", {})
            self._slug_to_path = data.get("slug_to_path", {})
        except Exception:
            pass

    def save(self) -> None:
        """Persist current index to disk. Thread-safe."""
        with self._lock:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(json.dumps({
                "path_to_slug": self._path_to_slug,
                "slug_to_path": self._slug_to_path,
                "updated_at":   datetime.now(timezone.utc).isoformat(),
            }, indent=2, ensure_ascii=False))

    def get_slug(self, path: str) -> Optional[str]:
        """Return the slug for *path*, or None if not registered."""
        return self._path_to_slug.get(path)

    def register(self, path: str, base_slug: str) -> str:
        """Return the (possibly suffix-incremented) slug for *path*, creating one if needed."""
        with self._lock:
            existing = self._path_to_slug.get(path)
            if existing:
                return existing

            slug = base_slug
            n = 2
            while slug in self._slug_to_path and self._slug_to_path[slug] != path:
                slug = f"{base_slug}__{n}"
                n += 1

            self._path_to_slug[path] = slug
            self._slug_to_path[slug] = path
            return slug

    def remove(self, path: str) -> None:
        """Remove *path* and its associated slug from the index."""
        with self._lock:
            slug = self._path_to_slug.pop(path, None)
            if slug:
                self._slug_to_path.pop(slug, None)
