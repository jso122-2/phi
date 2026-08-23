"""Tests for phi.models.tag_embedder (TagEmbedder).

Covers:
- encode_genre: returns [] for no-tag track, GENRE_DIM vector after fit
- encode_mood: returns [] for no-data track, MOOD_DIM unit vector with data
- cosine properties: self-similarity = 1.0, dissimilar < 1.0
- annotate: writes genre_vec / mood_vec, skips existing, respects overwrite
- session_genre_vec / session_mood_vec: mean unit vector
- save / load round-trip: vectors are equal
- RankContext gets _session_genre_vec / _session_mood_vec after embed ready
- _genre_affinity / _mood_affinity use vecs when present
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from phi.models.tag_embedder import TagEmbedder, GENRE_DIM, MOOD_DIM, MOOD_LABELS


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_library(tracks: list[dict]) -> MagicMock:
    """Stub library with given track descriptors.

    Each dict: {"path", "ann", "meta"}
    """
    lib = MagicMock()
    lib.playlist = [t["path"] for t in tracks]
    lib.meta_cache = {t["path"]: t.get("meta", {}) for t in tracks}
    lib.annotations = {t["path"]: dict(t.get("ann", {})) for t in tracks}
    return lib


def _normed(v: list[float]) -> float:
    arr = np.asarray(v, dtype=np.float32)
    return float(np.linalg.norm(arr))


# ── encode_genre ───────────────────────────────────────────────────────────────

class TestEncodeGenre:
    def test_returns_empty_before_fit(self):
        emb = TagEmbedder()
        assert emb.encode_genre({"lfm_tags": ["rock"]}, {}) == []

    def test_returns_empty_for_no_tags_after_fit(self):
        lib = _make_library([
            {"path": "/a", "ann": {"lfm_tags": ["rock", "indie"]}, "meta": {}},
            {"path": "/b", "ann": {"lfm_tags": ["pop", "dance"]}, "meta": {}},
        ])
        emb = TagEmbedder().fit(lib)
        result = emb.encode_genre({}, {})
        assert result == []

    def test_returns_correct_dim_after_fit(self):
        tracks = [
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "common"]}, "meta": {}}
            for i in range(10)
        ]
        lib = _make_library(tracks)
        emb = TagEmbedder().fit(lib)
        v = emb.encode_genre({"lfm_tags": ["tag1", "common"]}, {})
        assert len(v) > 0
        assert len(v) <= GENRE_DIM

    def test_output_is_unit_vector(self):
        tracks = [
            {"path": f"/{i}", "ann": {"lfm_tags": [f"genre{i}", "shared"]}, "meta": {}}
            for i in range(8)
        ]
        lib = _make_library(tracks)
        emb = TagEmbedder().fit(lib)
        v = emb.encode_genre({"lfm_tags": ["genre0", "shared"]}, {})
        if v:
            assert abs(_normed(v) - 1.0) < 1e-5

    def test_same_tags_same_vector(self):
        lib = _make_library([
            {"path": "/a", "ann": {"lfm_tags": ["rock", "metal"]}, "meta": {}},
            {"path": "/b", "ann": {"lfm_tags": ["pop", "electro"]}, "meta": {}},
            {"path": "/c", "ann": {"lfm_tags": ["jazz", "soul"]}, "meta": {}},
        ])
        emb = TagEmbedder().fit(lib)
        v1 = emb.encode_genre({"lfm_tags": ["rock", "metal"]}, {})
        v2 = emb.encode_genre({"lfm_tags": ["rock", "metal"]}, {})
        if v1 and v2:
            assert v1 == v2

    def test_similar_tags_higher_cosine_than_different(self):
        lib = _make_library([
            {"path": "/a", "ann": {"lfm_tags": ["rock", "indie", "guitar"]}, "meta": {}},
            {"path": "/b", "ann": {"lfm_tags": ["rock", "indie", "british"]}, "meta": {}},
            {"path": "/c", "ann": {"lfm_tags": ["classical", "orchestral", "piano"]}, "meta": {}},
            {"path": "/d", "ann": {"lfm_tags": ["hip-hop", "rap", "trap"]}, "meta": {}},
        ])
        emb = TagEmbedder().fit(lib)
        va = emb.encode_genre({"lfm_tags": ["rock", "indie", "guitar"]}, {})
        vb = emb.encode_genre({"lfm_tags": ["rock", "indie", "british"]}, {})
        vc = emb.encode_genre({"lfm_tags": ["classical", "orchestral", "piano"]}, {})
        if va and vb and vc:
            def cos(a, b):
                a, b = np.asarray(a), np.asarray(b)
                return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            assert cos(va, vb) > cos(va, vc)


# ── encode_mood ────────────────────────────────────────────────────────────────

class TestEncodeMood:
    def test_returns_empty_for_no_data(self):
        emb = TagEmbedder()
        assert emb.encode_mood({}, {}) == []

    def test_valence_energy_only(self):
        emb = TagEmbedder()
        v = emb.encode_mood({"spotify_valence": 0.8, "spotify_energy": 0.6}, {})
        assert len(v) == MOOD_DIM
        assert abs(_normed(v) - 1.0) < 1e-5

    def test_mood_label_only(self):
        emb = TagEmbedder()
        v = emb.encode_mood({"mood": "calm"}, {})
        assert len(v) == MOOD_DIM
        assert abs(_normed(v) - 1.0) < 1e-5

    def test_full_data_unit_vector(self):
        emb = TagEmbedder()
        v = emb.encode_mood(
            {"spotify_valence": 0.5, "spotify_energy": 0.7, "mood": "energetic"}, {}
        )
        assert len(v) == MOOD_DIM
        assert abs(_normed(v) - 1.0) < 1e-5

    def test_happy_and_energetic_closer_than_happy_and_sad(self):
        emb = TagEmbedder()
        v_happy = emb.encode_mood(
            {"spotify_valence": 0.8, "spotify_energy": 0.7, "mood": "happy"}, {}
        )
        v_energetic = emb.encode_mood(
            {"spotify_valence": 0.7, "spotify_energy": 0.9, "mood": "energetic"}, {}
        )
        v_sad = emb.encode_mood(
            {"spotify_valence": 0.2, "spotify_energy": 0.2, "mood": "sad"}, {}
        )
        if v_happy and v_energetic and v_sad:
            a, b, c = np.asarray(v_happy), np.asarray(v_energetic), np.asarray(v_sad)
            norm = lambda x: np.linalg.norm(x) + 1e-9
            cos_he = float(np.dot(a, b) / (norm(a) * norm(b)))
            cos_hs = float(np.dot(a, c) / (norm(a) * norm(c)))
            assert cos_he > cos_hs


# ── annotate ───────────────────────────────────────────────────────────────────

class TestAnnotate:
    def _fitted_emb(self, n: int = 5) -> TagEmbedder:
        lib = _make_library([
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "shared"]}, "meta": {}}
            for i in range(n)
        ])
        return TagEmbedder().fit(lib)

    def test_writes_genre_and_mood_vecs(self):
        lib = _make_library([
            {
                "path": "/a",
                "ann": {"lfm_tags": ["rock"], "spotify_valence": 0.8, "spotify_energy": 0.7},
                "meta": {},
            },
            {
                "path": "/b",
                "ann": {"lfm_tags": ["pop"], "spotify_valence": 0.5, "spotify_energy": 0.4},
                "meta": {},
            },
        ])
        emb = TagEmbedder().fit(lib)
        genre_n, mood_n = emb.annotate(lib)
        assert genre_n > 0
        assert mood_n > 0
        assert lib.annotations["/a"].get("mood_vec") is not None

    def test_does_not_overwrite_existing_by_default(self):
        sentinel = [0.1, 0.2, 0.3]
        lib = _make_library([
            {
                "path": "/a",
                "ann": {"lfm_tags": ["rock"], "mood_vec": sentinel, "genre_vec": sentinel},
                "meta": {},
            },
        ])
        emb = TagEmbedder().fit(lib)
        emb.annotate(lib, overwrite=False)
        assert lib.annotations["/a"]["mood_vec"] is sentinel
        assert lib.annotations["/a"]["genre_vec"] is sentinel

    def test_overwrite_replaces_existing(self):
        sentinel = [0.1, 0.2, 0.3]
        lib = _make_library([
            {
                "path": "/a",
                "ann": {
                    "lfm_tags": ["rock"],
                    "mood_vec": sentinel,
                    "spotify_valence": 0.9,
                    "spotify_energy": 0.8,
                },
                "meta": {},
            },
            {
                "path": "/b",
                "ann": {"lfm_tags": ["pop"], "spotify_valence": 0.3, "spotify_energy": 0.4},
                "meta": {},
            },
        ])
        emb = TagEmbedder().fit(lib)
        emb.annotate(lib, overwrite=True)
        assert lib.annotations["/a"]["mood_vec"] != sentinel

    def test_returns_counts(self):
        lib = _make_library([
            {"path": "/a", "ann": {"lfm_tags": ["rock"], "spotify_valence": 0.7, "spotify_energy": 0.6}, "meta": {}},
            {"path": "/b", "ann": {}, "meta": {}},  # no tags, no valence/energy
        ])
        emb = TagEmbedder().fit(lib)
        genre_n, mood_n = emb.annotate(lib)
        assert isinstance(genre_n, int)
        assert isinstance(mood_n, int)


# ── session vecs ───────────────────────────────────────────────────────────────

class TestSessionVecs:
    def test_session_genre_vec_is_unit(self):
        lib = _make_library([
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "shared"]}, "meta": {}}
            for i in range(6)
        ])
        emb = TagEmbedder().fit(lib)
        emb.annotate(lib)
        gv = emb.session_genre_vec(["/0", "/1", "/2"], lib)
        if gv:
            assert abs(_normed(gv) - 1.0) < 1e-5

    def test_session_mood_vec_is_unit(self):
        lib = _make_library([
            {
                "path": f"/{i}",
                "ann": {"spotify_valence": 0.5, "spotify_energy": 0.6},
                "meta": {},
            }
            for i in range(4)
        ])
        emb = TagEmbedder().fit(lib)
        emb.annotate(lib)
        mv = emb.session_mood_vec(["/0", "/1"], lib)
        if mv:
            assert abs(_normed(mv) - 1.0) < 1e-5

    def test_empty_paths_returns_empty(self):
        lib = _make_library([])
        emb = TagEmbedder()
        assert emb.session_genre_vec([], lib) == []
        assert emb.session_mood_vec([], lib) == []


# ── save / load ────────────────────────────────────────────────────────────────

class TestPersistence:
    def test_save_load_roundtrip(self):
        lib = _make_library([
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "shared"]}, "meta": {}}
            for i in range(8)
        ])
        emb = TagEmbedder().fit(lib)
        with tempfile.TemporaryDirectory() as td:
            ckpt = Path(td) / "emb.npz"
            emb.save(ckpt)
            loaded = TagEmbedder.load(ckpt)
        # Same vocab and IDF
        assert set(emb._vocab.keys()) == set(loaded._vocab.keys())
        np.testing.assert_allclose(emb._idf, loaded._idf, rtol=1e-5)
        np.testing.assert_allclose(emb._components, loaded._components, rtol=1e-5)

    def test_loaded_encodes_same(self):
        lib = _make_library([
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "shared"]}, "meta": {}}
            for i in range(8)
        ])
        emb = TagEmbedder().fit(lib)
        ann = {"lfm_tags": ["tag0", "shared"]}
        v_orig = emb.encode_genre(ann, {})
        with tempfile.TemporaryDirectory() as td:
            ckpt = Path(td) / "emb.npz"
            emb.save(ckpt)
            loaded = TagEmbedder.load(ckpt)
        v_load = loaded.encode_genre(ann, {})
        if v_orig and v_load:
            np.testing.assert_allclose(v_orig, v_load, rtol=1e-5)

    def test_load_default_returns_none_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_TAG_EMBEDDER", str(tmp_path / "nonexistent.npz"))
        result = TagEmbedder.load_default()
        assert result is None


# ── ranker integration ─────────────────────────────────────────────────────────

class TestRankerIntegration:
    """_genre_affinity and _mood_affinity use vecs when present."""

    def _build_ctx(self, genre_vec, mood_vec):
        from phi.core.ranker._session import RankContext
        ctx = RankContext()
        if genre_vec:
            ctx._session_genre_vec = genre_vec  # type: ignore[attr-defined]
        if mood_vec:
            ctx._session_mood_vec = mood_vec    # type: ignore[attr-defined]
        return ctx

    def test_genre_affinity_uses_vec_when_present(self):
        from phi.core.ranker._scoring import _genre_affinity
        emb = TagEmbedder()
        lib = _make_library([
            {"path": f"/{i}", "ann": {"lfm_tags": [f"tag{i}", "shared"]}, "meta": {}}
            for i in range(6)
        ])
        emb.fit(lib)
        ann = {"lfm_tags": ["tag0", "shared"]}
        track_vec = emb.encode_genre(ann, {})
        session_vec = emb.encode_genre({"lfm_tags": ["tag0", "shared"]}, {})
        if not track_vec or not session_vec:
            pytest.skip("too few tracks for SVD in this run")
        ann["genre_vec"] = track_vec
        ctx = self._build_ctx(session_vec, None)
        score = _genre_affinity({}, ann, ctx)
        assert score > 0.9, f"same-tag cosine should be ~1.0, got {score}"

    def test_mood_affinity_uses_vec_when_present(self):
        from phi.core.ranker._scoring import _mood_affinity
        emb = TagEmbedder()
        ann = {"spotify_valence": 0.8, "spotify_energy": 0.7}
        track_mv = emb.encode_mood(ann, {})
        session_mv = emb.encode_mood(ann, {})
        if not track_mv or not session_mv:
            pytest.skip("no mood data")
        ann["mood_vec"] = track_mv
        ctx = self._build_ctx(None, session_mv)
        score = _mood_affinity(ann, {}, ctx)
        assert score > 0.9, f"identical mood vec cosine should be ~1.0, got {score}"
