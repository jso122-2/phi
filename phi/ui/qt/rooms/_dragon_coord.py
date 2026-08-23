# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms._dragon_coord — BPM × Key → unit-square projection.

Pure math — no Qt, no I/O.  Used by dragon_room.MLDragonPage at track load
time to auto-compute the canvas anchor from a track's BPM and key signature.
"""
from __future__ import annotations

from typing import Optional

_BPM_LO: float = 60.0
_BPM_HI: float = 200.0

# Camelot slot [0..23]: same root interleaved (1A=minor=0, 1B=major=1, 2A=2, …)
_CAMELOT_SLOT: dict[str, int] = {
    "1A":  0, "1B":  1, "2A":  2, "2B":  3,
    "3A":  4, "3B":  5, "4A":  6, "4B":  7,
    "5A":  8, "5B":  9, "6A": 10, "6B": 11,
    "7A": 12, "7B": 13, "8A": 14, "8B": 15,
    "9A": 16, "9B": 17, "10A": 18, "10B": 19,
    "11A": 20, "11B": 21, "12A": 22, "12B": 23,
}

# Standard notation → Camelot (covers most tagger output formats)
_STD_TO_CAMELOT: dict[str, str] = {
    # Major keys
    "C":    "8B", "Cmaj": "8B",
    "G":    "9B", "Gmaj": "9B",
    "D":   "10B", "Dmaj": "10B",
    "A":   "11B", "Amaj": "11B",
    "E":   "12B", "Emaj": "12B",
    "B":    "1B", "Bmaj":  "1B",
    "F#":   "2B", "F#maj": "2B", "Gb": "2B", "Gbmaj": "2B",
    "Db":   "3B", "Dbmaj": "3B", "C#": "3B", "C#maj": "3B",
    "Ab":   "4B", "Abmaj": "4B", "G#": "4B", "G#maj": "4B",
    "Eb":   "5B", "Ebmaj": "5B", "D#": "5B", "D#maj": "5B",
    "Bb":   "6B", "Bbmaj": "6B", "A#": "6B", "A#maj": "6B",
    "F":    "7B", "Fmaj":  "7B",
    # Minor keys
    "Am":   "8A", "Amin":  "8A",
    "Em":   "9A", "Emin":  "9A",
    "Bm":  "10A", "Bmin": "10A",
    "F#m": "11A", "F#min":"11A", "Gbm": "11A",
    "C#m": "12A", "C#min":"12A", "Dbm": "12A",
    "G#m":  "1A", "G#min": "1A", "Abm":  "1A",
    "D#m":  "2A", "D#min": "2A", "Ebm":  "2A",
    "Bbm":  "3A", "Bbmin": "3A", "A#m":  "3A",
    "Fm":   "4A", "Fmin":  "4A",
    "Cm":   "5A", "Cmin":  "5A",
    "Gm":   "6A", "Gmin":  "6A",
    "Dm":   "7A", "Dmin":  "7A",
}


def _parse_camelot(key_sig: Optional[str]) -> Optional[int]:
    """
    Return Camelot slot [0..23] from a key string, or None if unparseable.

    Accepts: "4A", "11B" (native Camelot), "Am", "C#", "Fmaj", "Dm" (standard).
    """
    if not key_sig:
        return None
    k = key_sig.strip()
    upper = k.upper()
    if upper in _CAMELOT_SLOT:
        return _CAMELOT_SLOT[upper]
    camelot = _STD_TO_CAMELOT.get(k) or _STD_TO_CAMELOT.get(k.capitalize())
    if camelot:
        return _CAMELOT_SLOT[camelot]
    return None


def bpm_key_to_unit(
    bpm:     Optional[float],
    key_sig: Optional[str],
) -> tuple[float, float]:
    """
    Project (bpm, key_sig) → (x, y) ∈ [0, 1]².

        x = BPM normalised over [60, 200]   — tempo axis
        y = Camelot slot / 23               — harmonic axis (24 wheel positions)

    Falls back to 0.5 on each axis when data is missing.
    """
    try:
        bpm_f = float(bpm)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        bpm_f = None

    if bpm_f and bpm_f > 0:
        x = max(0.0, min(1.0, (bpm_f - _BPM_LO) / (_BPM_HI - _BPM_LO)))
    else:
        x = 0.5

    slot = _parse_camelot(key_sig)
    y = slot / 23.0 if slot is not None else 0.5

    return x, y
