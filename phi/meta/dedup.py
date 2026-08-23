# -*- coding: utf-8 -*-
"""phi.meta.dedup — fingerprint-based duplicate detection.

Two tracks are considered duplicates if their chromaprint fingerprints
hash to the same value.  The dedup pass runs after enrichment (so
fingerprints are already cached in Library.annotations) and is entirely
read-only — it never deletes files.  The UI presents groups to the user
for manual resolution.
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class DupGroup:
    """A set of files that are acoustically identical."""
    paths:     list[str]
    fp_prefix: str = ""          # first 16 chars of fingerprint (display only)

    def display_label(self) -> str:
        first = self.paths[0] if self.paths else ""
        name  = os.path.basename(first)
        return f"{name}  +{len(self.paths) - 1} duplicate{'s' if len(self.paths) > 2 else ''}"

    def sizes(self) -> list[int]:
        """File sizes in bytes for each path (for 'keep largest' heuristic)."""
        result = []
        for p in self.paths:
            try:
                result.append(os.path.getsize(p))
            except OSError:
                result.append(0)
        return result

    def best_candidate(self) -> str:
        """
        Return the path most likely to keep: largest file size
        (usually highest bit rate / uncompressed).
        """
        pairs = list(zip(self.paths, self.sizes()))
        pairs.sort(key=lambda t: -t[1])
        return pairs[0][0]


def find_duplicates(library) -> list[DupGroup]:
    """
    Scan *library* for tracks whose stored fingerprints are identical.

    Only considers tracks that have an 'acoustid_fp' key in their annotations
    (i.e. have been through the enrichment pipeline).  Tracks without a
    fingerprint are ignored.

    Returns a list of DupGroup — each group has len >= 2.
    """
    fp_to_paths: dict[str, list[str]] = defaultdict(list)

    for path in library.playlist:
        ann = library.get_annotation(path)
        fp  = ann.get("acoustid_fp")
        if fp:
            # Use a 40-char prefix — full chromaprint strings are very long
            key = fp[:40]
            fp_to_paths[key].append(path)

    groups: list[DupGroup] = []
    for fp_key, paths in fp_to_paths.items():
        if len(paths) >= 2:
            groups.append(DupGroup(paths=paths, fp_prefix=fp_key[:16]))

    # Sort by group size descending (most duplicates first)
    groups.sort(key=lambda g: -len(g.paths))
    return groups


def find_tag_duplicates(library) -> list[DupGroup]:
    """
    Fallback dedup that uses (title, artist) pairs instead of fingerprints.
    Less precise but useful before fingerprinting has run.
    """
    key_to_paths: dict[tuple, list[str]] = defaultdict(list)

    for path in library.playlist:
        meta   = library.get_meta(path) or {}
        title  = (meta.get("title")  or "").strip().lower()
        artist = (meta.get("artist") or "").strip().lower()
        if title:
            key_to_paths[(title, artist)].append(path)

    groups: list[DupGroup] = []
    for _, paths in key_to_paths.items():
        if len(paths) >= 2:
            groups.append(DupGroup(paths=paths))

    groups.sort(key=lambda g: -len(g.paths))
    return groups
