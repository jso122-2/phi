# -*- coding: utf-8 -*-
"""phi.models.bpm — BPM, key, energy, and mood models.

BPMModel priority chain:
  1. Existing tag (TBPM, BPM, tempo) via mutagen — instant, no compute.
  2. librosa.beat.beat_track() on a 90-second audio window — ~1–3 s per track.
  3. Returns {} / pending marker if neither source is available.

KeyModel priority chain:
  1. Existing tag (TKEY / initialkey) — instant.
  2. Krumhansl-Schmuckler chroma correlation via librosa — ~1–2 s per track.

EnergyModel, MoodModel: heuristic from ReplayGain / BPM annotations.
"""
from __future__ import annotations

import math

from phi.models.base import PhiModel


# ── BPMModel ──────────────────────────────────────────────────────────────────

class BPMModel(PhiModel):
    """Detect BPM from ID3/Vorbis tags, then fall back to librosa analysis."""

    name        = "bpm"
    version     = "1.0.0"
    description = "BPM from tags → librosa.beat.beat_track() audio analysis"

    def can_process(self, path: str, meta: dict) -> bool:
        return meta.get("bpm") is None

    def run(self, path: str, meta: dict) -> dict:
        bpm = self._from_tags(path)
        if bpm:
            return {"bpm": bpm, "bpm_source": "tag"}

        bpm = self._from_audio(path)
        if bpm:
            return {"bpm": bpm, "bpm_source": "librosa"}

        return {"bpm": None, "bpm_source": "pending"}

    @staticmethod
    def _from_tags(path: str) -> float | None:
        try:
            from mutagen import File as MFile
            f = MFile(path)
            if f is None or f.tags is None:
                return None
            for key in ("TBPM", "bpm", "BPM", "tempo", "TEMPO"):
                val = f.tags.get(key)
                if val:
                    raw = str(val[0]) if hasattr(val, "__getitem__") else str(val)
                    try:
                        v = float(raw.split(".")[0])
                        if 40 <= v <= 300:
                            return v
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
        return None

    @staticmethod
    def _from_audio(path: str) -> float | None:
        """Use librosa beat tracker on the first 90 seconds of audio."""
        try:
            import librosa
            import numpy as np
            y, sr = librosa.load(path, sr=None, mono=True, duration=90.0,
                                  res_type="kaiser_fast")
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            if hasattr(tempo, "__len__"):
                tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
            else:
                tempo = float(tempo)
            if 40.0 <= tempo <= 300.0:
                return round(tempo, 1)
        except Exception:
            pass
        return None


# ── Krumhansl-Schmuckler key profiles ─────────────────────────────────────────

# Original K-S profiles (1990) — 12 pitches starting at C
_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
             2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
             2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]

# Camelot wheel open-key notation for use in DJ mixing
_CAMELOT_MAJOR = ["8B", "3B", "10B", "5B", "12B", "7B",
                  "2B", "9B", "4B", "11B", "6B", "1B"]
_CAMELOT_MINOR = ["5A", "12A", "7A", "2A", "9A", "4A",
                  "11A", "6A", "1A", "8A", "3A", "10A"]


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx  = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy  = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _ks_key(chroma_mean: list[float]) -> tuple[str, str, float]:
    """
    Return (key_name, camelot, confidence) using the K-S correlation method.

    key_name  e.g. "C# minor"
    camelot   e.g. "12A"
    confidence Pearson r of the best match [0, 1]
    """
    best_r    = -2.0
    best_name = "C major"
    best_cam  = "8B"

    for i in range(12):
        rotated = chroma_mean[i:] + chroma_mean[:i]
        r_major = _pearson(rotated, _KS_MAJOR)
        r_minor = _pearson(rotated, _KS_MINOR)
        if r_major > best_r:
            best_r    = r_major
            best_name = f"{_NOTE_NAMES[i]} major"
            best_cam  = _CAMELOT_MAJOR[i]
        if r_minor > best_r:
            best_r    = r_minor
            best_name = f"{_NOTE_NAMES[i]} minor"
            best_cam  = _CAMELOT_MINOR[i]

    return best_name, best_cam, round(best_r, 3)


# ── KeyModel ──────────────────────────────────────────────────────────────────

class KeyModel(PhiModel):
    """Detect musical key from tags, then fall back to chroma analysis."""

    name        = "key"
    version     = "1.0.0"
    description = "Key from tags → librosa chroma + Krumhansl-Schmuckler"

    def can_process(self, path: str, meta: dict) -> bool:
        return meta.get("key") is None

    def run(self, path: str, meta: dict) -> dict:
        key = self._from_tags(path)
        if key:
            return {"key": key, "key_source": "tag"}

        return self._from_audio(path)

    @staticmethod
    def _from_tags(path: str) -> str | None:
        try:
            from mutagen import File as MFile
            f = MFile(path)
            if f and f.tags:
                for tag_key in ("TKEY", "key", "KEY", "initialkey", "INITIALKEY"):
                    val = f.tags.get(tag_key)
                    if val:
                        k = str(val[0]) if hasattr(val, "__getitem__") else str(val)
                        k = k.strip()
                        if k:
                            return k
        except Exception:
            pass
        return None

    @staticmethod
    def _from_audio(path: str) -> dict:
        """Compute chroma mean and apply K-S key profiles."""
        try:
            import librosa
            import numpy as np
            y, sr = librosa.load(path, sr=None, mono=True, duration=60.0,
                                  res_type="kaiser_fast")
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = list(float(v) for v in np.mean(chroma, axis=1))
            key_name, camelot, confidence = _ks_key(chroma_mean)
            return {
                "key":            key_name,
                "key_camelot":    camelot,
                "key_confidence": confidence,
                "key_source":     "librosa",
            }
        except Exception:
            pass
        return {"key": None, "key_source": "pending"}


# ── EnergyModel ───────────────────────────────────────────────────────────────

class EnergyModel(PhiModel):
    """
    Estimate perceived energy [0, 1] from available tag signals.

    Priority chain:
      1. ReplayGain / R128 track gain tag  → map dB headroom to energy
      2. BPM proxy                          → higher BPM ≈ higher energy
      3. No signal available               → returns {}
    """

    name        = "energy"
    version     = "0.1.0"
    description = "Heuristic energy estimate from ReplayGain / BPM tags"

    _GAIN_KEYS = (
        "REPLAYGAIN_TRACK_GAIN",
        "replaygain_track_gain",
        "TXXX:replaygain_track_gain",
        "----:com.apple.iTunes:replaygain_track_gain",
    )

    def can_process(self, path: str, meta: dict) -> bool:
        return meta.get("energy") is None

    def run(self, path: str, meta: dict) -> dict:
        gain_db = self._read_gain(path)
        if gain_db is not None:
            energy = max(0.0, min(1.0, (6.0 - gain_db) / 24.0))
            return {"energy": round(energy, 3), "energy_source": "replaygain"}

        bpm = meta.get("bpm")
        if bpm:
            try:
                bpm_f  = float(bpm)
                energy = max(0.0, min(1.0, (bpm_f - 60.0) / 140.0))
                return {"energy": round(energy, 3), "energy_source": "bpm_proxy"}
            except (TypeError, ValueError):
                pass

        return {}

    def _read_gain(self, path: str) -> float | None:
        try:
            from mutagen import File as MFile
            f = MFile(path)
            if f is None or f.tags is None:
                return None
            for key in self._GAIN_KEYS:
                val = f.tags.get(key)
                if val:
                    raw = str(val[0]) if hasattr(val, "__getitem__") else str(val)
                    raw = raw.replace("dB", "").replace("LU", "").strip()
                    return float(raw)
        except Exception:
            pass
        return None


# ── MoodModel ─────────────────────────────────────────────────────────────────

class MoodModel(PhiModel):
    """
    Classify track mood from BPM + energy into four buckets.

        calm      — BPM < 85 or energy < 0.25
        chill     — BPM 85–115, energy < 0.60
        focused   — BPM 115–138, energy 0.35–0.70
        energetic — BPM > 138 or energy > 0.70

    Superseded by CLAPModel when torch + transformers are available.
    """

    name        = "mood"
    version     = "0.2.0"
    description = "Heuristic mood from BPM + energy; upgraded by CLAP when available"

    def can_process(self, path: str, meta: dict) -> bool:
        if meta.get("mood_source") == "clap":
            return False
        return meta.get("mood") is None

    def run(self, path: str, meta: dict) -> dict:
        bpm    = meta.get("bpm")
        energy = meta.get("energy")

        try:
            bpm = float(bpm) if bpm is not None else None
        except (TypeError, ValueError):
            bpm = None

        try:
            energy = float(energy) if energy is not None else None
        except (TypeError, ValueError):
            energy = None

        if bpm is None and energy is None:
            return {}

        mood = self._classify(bpm, energy)
        return {"mood": mood, "mood_source": "heuristic"}

    @staticmethod
    def _classify(bpm: float | None, energy: float | None) -> str:
        b = bpm    or 100.0
        e = energy or 0.45
        if b < 85 or e < 0.25:
            return "calm"
        if b > 138 or e > 0.70:
            return "energetic"
        if b >= 115:
            return "focused"
        return "chill"


# ── EmbeddingModel ────────────────────────────────────────────────────────────

class EmbeddingModel(PhiModel):
    """
    Audio embedding stub — deferred to CLAPModel when available.

    This class remains registered so the Models tab shows the slot,
    but can_process() always returns False; CLAPModel writes mood_vec
    (the actual embedding) directly.
    """

    name        = "embedding"
    version     = "0.1.0"
    description = "Embedding slot — provided by CLAPModel (torch + transformers)"

    def can_process(self, path: str, meta: dict) -> bool:
        return False

    def run(self, path: str, meta: dict) -> dict:
        return {}
