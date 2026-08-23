"""phi.models._metadata_encoder — metadata → 512-d feature vector."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from phi._track import CHROMATIC_KEYS, Track

D_IN: int = 512
TAG_VOCAB_SIZE: int = 256

# Mood label order — matches phi.models.tag_embedder.MOOD_LABELS.
# Dims [276:283]: one-hot over these 7 labels.
_MOOD_LABELS: tuple[str, ...] = (
    "calm", "chill", "focused", "energetic", "happy", "sad", "angry",
)
_MOOD_IDX: dict[str, int] = {m: i for i, m in enumerate(_MOOD_LABELS)}


class MetadataEncoder:
    """
    Encodes Track JSON metadata into a 512-d feature vector for CLAPProjection.

    Feature layout (512 dims):
        [0:12]    key one-hot (chromatic: C C# D D# E F F# G G# A A# B)
        [12]      key_confidence ∈ [0, 1]
        [13]      duration_s  log1p(s) / log1p(600)
        [14]      lfm_playcount  log1p(count) / 20
        [15]      lfm_listeners  log1p(count) / 20
        [16]      explicit  {0, 1}
        [17:273]  lfm_tags multi-hot over top-256 vocab

        Consensus dims (filled when ann dict is supplied):
        [273]     valence             Spotify ∈ [0, 1]  (0 when unknown)
        [274]     energy              Spotify ∈ [0, 1]  (0 when unknown)
        [275]     bpm_norm            log1p(bpm_consensus) / log1p(300)
        [276:283] mood_onehot         one-hot over 7 labels (calm…angry)
        [283]     buoyancy            catalog coverage × agreement ∈ [0, 1]
        [284:512] zeros               reserved

    Call set_vocab(tag_vocabulary_list) once after scanning the library.
    Pass ann=<annotation dict> to encode_one / encode to fill consensus dims.
    """

    def __init__(self) -> None:
        self._tag_vocab: list[str] = []
        self._tag_index: dict[str, int] = {}

    def set_vocab(self, tags: list[str]) -> None:
        self._tag_vocab = [t.lower() for t in tags[:TAG_VOCAB_SIZE]]
        self._tag_index = {t: i for i, t in enumerate(self._tag_vocab)}

    @property
    def vocab_size(self) -> int:
        return len(self._tag_vocab)

    def encode_one(self, track: Track, ann: Optional[dict] = None) -> np.ndarray:
        """Encode a single Track → (512,) float64.

        Parameters
        ----------
        track : Track sidecar fields (key, duration, Last.fm counts, tags).
        ann   : annotation dict from Library.annotations[path].  When supplied,
                consensus dims [273:284] are filled from buoyancy + Spotify
                numerics; otherwise those dims remain zero.
        """
        vec = np.zeros(D_IN, dtype=np.float64)

        key_clean = track.key.strip().replace("b", "#")
        enharmonic = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        key_clean = enharmonic.get(key_clean, key_clean)
        if key_clean in CHROMATIC_KEYS:
            vec[CHROMATIC_KEYS.index(key_clean)] = 1.0

        vec[12] = max(0.0, min(1.0, float(track.key_confidence)))
        vec[13] = math.log1p(max(0.0, track.duration_s)) / math.log1p(600.0)
        vec[14] = math.log1p(max(0, track.lfm_playcount)) / 20.0
        vec[15] = math.log1p(max(0, track.lfm_listeners)) / 20.0
        vec[16] = 1.0 if track.explicit else 0.0

        for tag in track.lfm_tags:
            idx = self._tag_index.get(tag.lower())
            if idx is not None:
                vec[17 + idx] = 1.0

        # ── Consensus dims [273:284] — filled only when annotations are supplied ──
        if ann:
            vec[273] = max(0.0, min(1.0, float(ann.get("spotify_valence") or 0.0)))
            vec[274] = max(0.0, min(1.0, float(ann.get("spotify_energy")  or 0.0)))
            bpm = float(ann.get("bpm_consensus") or ann.get("spotify_tempo") or 0.0)
            if bpm > 0:
                vec[275] = min(1.0, math.log1p(bpm) / math.log1p(300.0))
            mood = (ann.get("spotify_mood") or ann.get("mood") or "").lower().strip()
            mood_idx = _MOOD_IDX.get(mood)
            if mood_idx is not None:
                vec[276 + mood_idx] = 1.0
            vec[283] = max(0.0, min(1.0, float(ann.get("buoyancy") or 0.0)))

        return vec

    def encode(
        self,
        tracks: list[Track],
        annotations: Optional[dict[str, dict]] = None,
    ) -> np.ndarray:
        """Encode list of tracks → (N, 512) float64.

        Parameters
        ----------
        tracks      : Track objects.
        annotations : optional {path: ann_dict} mapping.  When supplied, each
                      track's annotation dict is looked up by ``str(track.path)``
                      and passed to encode_one to fill consensus dims.
        """
        anns = annotations or {}
        return np.stack(
            [self.encode_one(t, ann=anns.get(str(t.path))) for t in tracks],
            axis=0,
        )

    def __repr__(self) -> str:
        return f"<MetadataEncoder vocab_size={self.vocab_size}>"
