# -*- coding: utf-8 -*-
"""phi.meta.acoustid_client — chromaprint fingerprinting + AcoustID lookup.

Wraps pyacoustid (which wraps fpcalc / libchromaprint) and the AcoustID
web API.  All network calls are synchronous — run on a background thread.

Typical flow
------------
1. fingerprint(path) → (fingerprint_str, duration_secs)
2. lookup(api_key, fingerprint, duration) → list[AcoustIDResult]
3. best_match(results, threshold=0.70) → AcoustIDResult | None
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


# ── result types ──────────────────────────────────────────────────────────────

@dataclass
class AcoustIDRecording:
    """A single MusicBrainz recording returned inside an AcoustID result."""
    mbid:   str
    title:  Optional[str]  = None
    artists: list[dict]    = field(default_factory=list)
    releases: list[dict]   = field(default_factory=list)


@dataclass
class AcoustIDResult:
    """One candidate match from the AcoustID service."""
    acoustid:   str                          # AcoustID identifier
    score:      float                        # confidence [0.0, 1.0]
    recordings: list[AcoustIDRecording] = field(default_factory=list)

    @property
    def best_recording(self) -> Optional[AcoustIDRecording]:
        """Return the first recording (AcoustID usually returns one per result)."""
        return self.recordings[0] if self.recordings else None


# ── fingerprinting ─────────────────────────────────────────────────────────────

def fingerprint(path: str) -> tuple[str, int]:
    """
    Generate a chromaprint fingerprint for the audio file at *path*.

    Returns
    -------
    (fingerprint_str, duration_seconds)

    Raises
    ------
    RuntimeError  if fpcalc / libchromaprint is not available
    Exception     on any other failure (corrupt file, etc.)
    """
    try:
        import acoustid
        duration, fp = acoustid.fingerprint_file(path)
        return fp.decode() if isinstance(fp, bytes) else fp, int(duration)
    except ImportError as exc:
        raise RuntimeError(
            "pyacoustid / chromaprint not available. "
            "Install with: brew install chromaprint && pip install pyacoustid"
        ) from exc


# ── AcoustID web API ───────────────────────────────────────────────────────────

_ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
_META_FLAGS   = "recordings+releasegroups+compress"


def lookup(
    api_key:     str,
    fingerprint: str,
    duration:    int,
    *,
    timeout:     float = 10.0,
) -> list[AcoustIDResult]:
    """
    Query the AcoustID web service and return a list of candidate matches.

    Parameters
    ----------
    api_key     AcoustID application API key
    fingerprint chromaprint fingerprint string (from fingerprint())
    duration    track duration in seconds
    timeout     request timeout in seconds

    Returns an empty list on any network / parse failure rather than raising.
    """
    try:
        import acoustid
        results: list[AcoustIDResult] = []

        for score, recording_id, title, artist in acoustid.parse_lookup_result(
            acoustid.lookup(api_key, fingerprint, duration, meta=_META_FLAGS)
        ):
            rec = AcoustIDRecording(
                mbid=recording_id or "",
                title=title,
                artists=[{"name": artist}] if artist else [],
            )
            results.append(AcoustIDResult(
                acoustid="",
                score=score,
                recordings=[rec] if recording_id else [],
            ))

        return results

    except Exception:
        return []


def lookup_raw(
    api_key:     str,
    fingerprint: str,
    duration:    int,
    *,
    timeout:     float = 10.0,
) -> list[AcoustIDResult]:
    """
    Variant that parses the full AcoustID JSON response for richer data
    (release MBIDs, artist MBIDs).  Falls back to lookup() on import errors.
    """
    try:
        import requests
    except ImportError:
        return lookup(api_key, fingerprint, duration, timeout=timeout)

    try:
        resp = requests.get(
            _ACOUSTID_URL,
            params={
                "client":      api_key,
                "fingerprint": fingerprint,
                "duration":    duration,
                "meta":        _META_FLAGS,
                "format":      "json",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    if data.get("status") != "ok":
        return []

    results: list[AcoustIDResult] = []
    for item in data.get("results", []):
        score     = float(item.get("score", 0.0))
        acoustid_ = item.get("id", "")
        recordings: list[AcoustIDRecording] = []

        for rec_raw in item.get("recordings", []):
            artists  = rec_raw.get("artists", [])
            releases = rec_raw.get("releasegroups", [])
            recordings.append(AcoustIDRecording(
                mbid=rec_raw.get("id", ""),
                title=rec_raw.get("title"),
                artists=artists,
                releases=releases,
            ))

        results.append(AcoustIDResult(
            acoustid=acoustid_,
            score=score,
            recordings=recordings,
        ))

    # Sort by descending confidence
    results.sort(key=lambda r: -r.score)
    return results


# ── helpers ───────────────────────────────────────────────────────────────────

def best_match(
    results:   list[AcoustIDResult],
    threshold: float = 0.70,
) -> Optional[AcoustIDResult]:
    """
    Return the highest-scoring result whose score ≥ *threshold* and
    that has at least one recording with a non-empty MBID.

    Returns None if no result meets the bar.
    """
    for r in results:  # already sorted by score descending
        if r.score >= threshold and r.best_recording and r.best_recording.mbid:
            return r
    return None
