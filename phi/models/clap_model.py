# -*- coding: utf-8 -*-
"""phi.models.clap_model — CLAP-based mood + genre vector extraction.

Lazy ML upgrade for MoodModel and genre affinity.

When ``torch`` and ``transformers`` are importable and
``laion/clap-htsat-fused`` is available, this model runs each audio file
through CLAP to produce:

    mood_vec   : list[float]  — 512-d audio embedding (mood-sensitive)
    genre_vec  : list[float]  — same embedding reused; ranker uses it for
                               cosine genre affinity
    mood_source: "clap"       — signals MoodModel to skip re-classification

When dependencies are absent, ``can_process()`` returns False and the model
is silently skipped — the heuristic MoodModel continues to run instead.

Registration
------------
Add to ModelRegistry after MoodModel so it can supersede heuristic results:

    from phi.models.clap_model import CLAPModel
    registry.register(CLAPModel())

The registry runs models sequentially per track, so CLAPModel will overwrite
heuristic mood annotations with higher-quality CLAP-derived vectors.

Dependencies (optional)
-----------------------
    pip install torch transformers librosa soundfile

Model is loaded once (lazy singleton) and kept in RAM across batch runs.
On CPU-only machines this is ~350 MB and runs in ~1–3s per track.
"""
from __future__ import annotations

import io
import math
from typing import TYPE_CHECKING

from phi.models.base import PhiModel

if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor

# Floor subscription — set by bind_floor(); signals when embedding space shifts
_floor = None
_needs_reprocess: bool = False


def needs_reprocess() -> bool:
    """True when the MATH hub has signalled an embedding-space shift.

    Read by MetaWorker.schedule_model_run() to expand the annotation pass to
    all unannotated library tracks, not just the newly-added ones.
    """
    return _needs_reprocess


def clear_reprocess() -> None:
    """Reset the reprocess flag after the annotation pass has been scheduled."""
    global _needs_reprocess
    _needs_reprocess = False

# ── CLAP availability check (60s cache) ───────────────────────────────────────
_clap_available:  bool | None = None
_clap_checked_at: float       = 0.0


def bind_floor(floor: "ForestFloor") -> None:
    """Subscribe CLAPModel to the MATH hub (shard 3) on the forest floor.

    When MATH hub loses coherence (τ≈19.5, after ~20 CLAP batches or a
    large mycelial surge), the _needs_reprocess flag is raised.  The next
    call to CLAPModel.process() checks this flag and prioritises tracks
    that may need re-embedding (e.g. tracks whose features have changed
    since the last run).

    Called once by PhiApp after the floor is instantiated.
    """
    global _floor
    _floor = floor

    def _on_math_shift(result, payload: dict) -> None:
        global _needs_reprocess
        if result.should_act:
            _needs_reprocess = True

    floor.when_floor_shifts(shard=3, handler=_on_math_shift)


# Mood label vocabulary used for zero-shot classification
_MOOD_LABELS = ["calm", "chill", "focused", "energetic"]

# Text prompts fed to CLAP's text encoder for each mood label
_MOOD_PROMPTS = {
    "calm":      "calm, ambient, peaceful music",
    "chill":     "chill, relaxed, laid-back music",
    "focused":   "focused, mid-tempo, driven music",
    "energetic": "energetic, fast, high-energy music",
}

# Genre prompts (broad — used for genre_vec similarity at ranking time)
_GENRE_PROMPTS = {
    "electronic": "electronic, synth, dance music",
    "rock":       "rock, guitar, drums music",
    "hip hop":    "hip hop, rap music",
    "jazz":       "jazz, blues, soul music",
    "classical":  "classical, orchestral music",
    "pop":        "pop music",
    "metal":      "metal, heavy music",
    "folk":       "folk, acoustic music",
    "r&b":        "r&b, soul music",
    "ambient":    "ambient, drone, soundscape music",
}


class CLAPModel(PhiModel):
    """
    CLAP-based mood and genre vector extractor.

    Produces mood_vec and genre_vec (512-d float lists) stored in annotations.
    Also writes mood (string label) and mood_source="clap" to supersede the
    heuristic MoodModel result.
    """

    name        = "clap"
    version     = "0.1.0"
    description = "CLAP audio embeddings for mood + genre vectors (requires torch + transformers)"

    _processor = None
    _model     = None
    _text_vecs: dict[str, list[float]] = {}   # pre-computed text embeddings

    @classmethod
    def _load(cls) -> bool:
        """Lazy-load the CLAP model.  Returns True if successful.

        Uses local_files_only=True so the call never touches the network.
        If the model isn't in the HuggingFace cache this returns False
        silently — the heuristic MoodModel continues to run instead.
        """
        if cls._model is not None:
            return True
        try:
            import os
            # Prevent the hub client from making any network requests.
            # Without this, from_pretrained() spawns retry threads that can
            # trigger a GIL-release crash on macOS when called from a
            # background thread with Tk's main loop running.
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

            from transformers import ClapModel, ClapProcessor
            cls._processor = ClapProcessor.from_pretrained(
                "laion/clap-htsat-fused", local_files_only=True
            )
            cls._model = ClapModel.from_pretrained(
                "laion/clap-htsat-fused", local_files_only=True
            )
            cls._model.eval()
            cls._precompute_text_vecs()
            return True
        except Exception:
            return False

    @classmethod
    def _precompute_text_vecs(cls) -> None:
        """Pre-compute text embeddings for all mood and genre prompts."""
        import torch
        import torch.nn.functional as F
        all_prompts = {**_MOOD_PROMPTS, **_GENRE_PROMPTS}
        texts  = list(all_prompts.values())
        labels = list(all_prompts.keys())
        with torch.inference_mode():
            inputs = cls._processor(text=texts, return_tensors="pt", padding=True, truncation=True)
            out    = cls._model.get_text_features(**inputs)
            # transformers ≥ 5.x returns an output object; older returns tensor directly
            vecs   = out.pooler_output if hasattr(out, "pooler_output") else out
            vecs   = F.normalize(vecs, dim=-1)
        for label, vec in zip(labels, vecs):
            cls._text_vecs[label] = vec.tolist()

    # ── PhiModel interface ────────────────────────────────────────────────────

    def can_process(self, path: str, meta: dict) -> bool:
        if meta.get("mood_source") == "clap":
            return False
        # Only activate if dependencies are present
        try:
            import torch          # noqa: F401
            import transformers   # noqa: F401
        except ImportError:
            return False
        # Skip if the model isn't locally cached — avoids network retries
        # and the macOS GIL crash they trigger in background threads.
        # Cache the result for 60 s to avoid per-track file I/O.
        import time
        global _clap_available, _clap_checked_at
        now = time.monotonic()
        if _clap_available is not None and now - _clap_checked_at < 60.0:
            return _clap_available
        try:
            from huggingface_hub import try_to_load_from_cache
            _clap_available = (
                try_to_load_from_cache("laion/clap-htsat-fused", "config.json") is not None
            )
        except Exception:
            _clap_available = False
        _clap_checked_at = now
        return _clap_available

    def run(self, path: str, meta: dict) -> dict:
        if not self._load():
            return {}

        audio_vec = self._encode_audio(path)
        if audio_vec is None:
            return {}

        # Zero-shot mood classification via cosine similarity to text prompts
        mood_sims = {
            label: _cosine(audio_vec, self._text_vecs[label])
            for label in _MOOD_LABELS
            if label in self._text_vecs
        }
        if not mood_sims:
            return {}

        best_mood = max(mood_sims, key=lambda k: mood_sims[k])

        # Genre vector — average of the top-2 genre text embeddings weighted by sim
        genre_sims = {
            label: _cosine(audio_vec, self._text_vecs[label])
            for label in _GENRE_PROMPTS
            if label in self._text_vecs
        }
        genre_vec = audio_vec   # default: use raw audio vec for genre similarity

        return {
            "mood":        best_mood,
            "mood_source": "clap",
            "mood_vec":    audio_vec,
            "genre_vec":   genre_vec,
            "mood_scores": mood_sims,
        }

    # ── audio encoding ────────────────────────────────────────────────────────

    @classmethod
    def _encode_audio(cls, path: str) -> list[float] | None:
        """Load audio, pass through CLAP, return L2-normalised 512-d vector.

        Uses librosa.load() which handles all common formats (wav, flac, mp3,
        ogg, mp4, m4a, aac) via soundfile with an audioread → ffmpeg fallback.

        Two-pass strategy for long files:
          1. librosa.get_duration() reads the header only (fast, no decode).
          2. librosa.load(offset, duration=10) decodes only the centre 10 s.
        Short files (≤ 10 s) are loaded in one pass with no offset.
        """
        try:
            import torch
            import torch.nn.functional as F
            import librosa

            _CLIP_S = 10.0
            _SR = 48_000

            total_s = librosa.get_duration(path=path)
            if total_s > _CLIP_S:
                offset_s = max(0.0, total_s / 2 - _CLIP_S / 2)
                audio, _ = librosa.load(
                    path, sr=_SR, mono=True,
                    offset=offset_s, duration=_CLIP_S,
                )
            else:
                audio, _ = librosa.load(path, sr=_SR, mono=True)

            with torch.inference_mode():
                inputs = cls._processor(
                    audio=audio,
                    sampling_rate=_SR,
                    return_tensors="pt",
                    padding=True,
                )
                out = cls._model.get_audio_features(**inputs)
                # transformers ≥ 5.x returns an output object; older returns tensor
                vec = out.pooler_output if hasattr(out, "pooler_output") else out
                vec = F.normalize(vec, dim=-1)
            return vec[0].tolist()
        except Exception:
            return None


# ── utilities ─────────────────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (mag_a * mag_b)))
