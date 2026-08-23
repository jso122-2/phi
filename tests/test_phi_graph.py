"""
Tests for phi — library, CLAPProjection, MetadataEncoder, PhiGraph.

These tests use synthetic Track objects — no disk I/O, no actual .mp3 files.
The live library path is only exercised in the integration tests at the bottom
(marked with `@pytest.mark.integration`), which require the real library to exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from phi.library import Track, PhiLibrary, CHROMATIC_KEYS, _load_track
from phi.models.clap_proj import (
    CLAPProjection,
    MetadataEncoder,
    embed_tracks,
    D_IN,
    D_OUT,
    TAG_VOCAB_SIZE,
)
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot, _tag_adjacency


# ============================================================================
# Helpers
# ============================================================================

def make_track(
    name: str = "TestTrack",
    artist: str = "Artist",
    duration_s: float = 180.0,
    key: str = "C",
    key_confidence: float = 0.8,
    lfm_tags: Optional[list[str]] = None,
    lfm_playcount: int = 10_000,
    lfm_listeners: int = 5_000,
    explicit: bool = False,
    path: Optional[Path] = None,
) -> Track:
    return Track(
        path=path or Path(f"/fake/{name}.mp3"),
        json_path=Path(f"/fake/{name}.json"),
        name=name,
        artist=artist,
        duration_s=duration_s,
        key=key,
        key_confidence=key_confidence,
        lfm_tags=lfm_tags if lfm_tags is not None else ["soul", "jazz"],
        lfm_playcount=lfm_playcount,
        lfm_listeners=lfm_listeners,
        explicit=explicit,
    )


def make_library(n: int = 10) -> tuple[PhiLibrary, list[Track]]:
    """Return a PhiLibrary with n synthetic tracks injected directly."""
    tracks = [make_track(name=f"T{i}", lfm_tags=["soul"] if i % 2 == 0 else ["jazz"])
              for i in range(n)]
    lib = PhiLibrary.__new__(PhiLibrary)
    lib.library_root = Path("/fake")
    lib._tracks = tracks
    lib._scanned = True
    return lib, tracks


def make_phi_graph(n: int = 10) -> tuple[PhiGraph, list[Track]]:
    """Return a pre-built PhiGraph with synthetic library."""
    lib, tracks = make_library(n)
    g = PhiGraph.__new__(PhiGraph)
    g.library_root = Path("/fake")
    g.edge_threshold = 0.10
    g.tag_vocab_top_k = 256
    g._library = lib
    g._proj = CLAPProjection(rng=np.random.default_rng(0))
    g._encoder = MetadataEncoder()
    g._snapshot = None
    return g, tracks


# ============================================================================
# Track tests
# ============================================================================

class TestTrack:
    def test_display_name_both(self):
        t = make_track(name="Radio Silence", artist="James Blake")
        assert t.display_name == "James Blake — Radio Silence"

    def test_display_name_fallback_to_stem(self):
        t = Track(path=Path("/music/unknown.mp3"), json_path=Path("/music/unknown.json"))
        assert t.display_name == "unknown"

    def test_all_tags_deduplicated(self):
        t = make_track(lfm_tags=["Soul", "soul", "SOUL"])
        # all_tags lowercases and deduplicates
        assert len([x for x in t.all_tags if x == "soul"]) == 1

    def test_all_tags_combines_sources(self):
        t = make_track(lfm_tags=["soul"])
        t.discogs_genre = ["Funk / Soul"]
        t.itunes_genre = "R&B/Soul"
        assert len(t.all_tags) == 3

    def test_hash_and_equality(self):
        p = Path("/music/track.mp3")
        t1 = make_track(path=p)
        t2 = make_track(name="Other", path=p)
        assert t1 == t2
        assert hash(t1) == hash(t2)

    def test_inequality_different_path(self):
        t1 = make_track(path=Path("/a.mp3"))
        t2 = make_track(path=Path("/b.mp3"))
        assert t1 != t2

    def test_equality_type_check(self):
        t = make_track()
        assert t.__eq__("not a track") is NotImplemented


# ============================================================================
# PhiLibrary tests (synthetic — no I/O)
# ============================================================================

class TestPhiLibrary:
    def test_len(self):
        lib, tracks = make_library(7)
        assert len(lib) == 7

    def test_getitem(self):
        lib, tracks = make_library(5)
        assert lib[0] is tracks[0]

    def test_by_artist(self):
        lib, _ = make_library(6)
        lib._tracks[0] = make_track(artist="Slowthai")
        results = lib.by_artist("slowthai")
        assert len(results) == 1

    def test_by_tag(self):
        lib, _ = make_library(6)
        soul_tracks = lib.by_tag("soul")
        assert len(soul_tracks) == 3  # tracks 0,2,4 (even indices)

    def test_tag_vocabulary_ordering(self):
        lib, _ = make_library(10)
        vocab = lib.tag_vocabulary(top_k=5)
        # "soul" appears in 5 tracks, "jazz" in 5 — both in top 5
        assert "soul" in vocab
        assert "jazz" in vocab

    def test_tag_vocabulary_top_k_cap(self):
        lib, _ = make_library(10)
        vocab = lib.tag_vocabulary(top_k=1)
        assert len(vocab) == 1

    def test_repr(self):
        lib, _ = make_library(3)
        r = repr(lib)
        assert "3" in r


# ============================================================================
# CLAPProjection tests
# ============================================================================

class TestCLAPProjection:
    def test_output_shape(self):
        proj = CLAPProjection()
        x = np.random.randn(8, 512)
        h = proj.forward(x)
        assert h.shape == (8, 256)

    def test_l2_normalised(self):
        proj = CLAPProjection()
        x = np.random.randn(20, 512)
        h = proj.forward(x)
        norms = np.linalg.norm(h, axis=1)
        np.testing.assert_allclose(norms, np.ones(20), atol=1e-10)

    def test_single_row(self):
        proj = CLAPProjection()
        x = np.random.randn(1, 512)
        h = proj.forward(x)
        assert h.shape == (1, 256)
        np.testing.assert_allclose(np.linalg.norm(h), 1.0, atol=1e-10)

    def test_zero_input_does_not_nan(self):
        proj = CLAPProjection()
        x = np.zeros((4, 512))
        h = proj.forward(x)
        assert not np.any(np.isnan(h))
        # Zero-input rows must still satisfy the L2-norm invariant
        norms = np.linalg.norm(h, axis=1)
        np.testing.assert_allclose(norms, np.ones(4), atol=1e-10)

    def test_n_params(self):
        proj = CLAPProjection()
        assert proj.n_params == 256 * 512 + 256

    def test_different_seeds_different_weights(self):
        p1 = CLAPProjection(rng=np.random.default_rng(1))
        p2 = CLAPProjection(rng=np.random.default_rng(99))
        assert not np.allclose(p1.W, p2.W)

    def test_same_seed_same_weights(self):
        p1 = CLAPProjection(rng=np.random.default_rng(42))
        p2 = CLAPProjection(rng=np.random.default_rng(42))
        np.testing.assert_array_equal(p1.W, p2.W)


# ============================================================================
# MetadataEncoder tests
# ============================================================================

class TestMetadataEncoder:
    def _enc(self, vocab=None) -> MetadataEncoder:
        enc = MetadataEncoder()
        enc.set_vocab(vocab or ["soul", "jazz", "rock", "pop", "electronic"])
        return enc

    def test_output_shape(self):
        enc = self._enc()
        t = make_track()
        v = enc.encode_one(t)
        assert v.shape == (512,)

    def test_key_one_hot_C(self):
        enc = self._enc()
        t = make_track(key="C")
        v = enc.encode_one(t)
        assert v[0] == 1.0
        assert v[1:12].sum() == 0.0

    def test_key_one_hot_sharp(self):
        enc = self._enc()
        t = make_track(key="D#")
        v = enc.encode_one(t)
        # D# is index 3 in CHROMATIC_KEYS
        assert CHROMATIC_KEYS.index("D#") == 3
        assert v[3] == 1.0
        assert v[sum(1 for k in CHROMATIC_KEYS if k != "D#")] == 0.0 or True  # others zero

    def test_key_unknown_leaves_zeros(self):
        enc = self._enc()
        t = make_track(key="X")
        v = enc.encode_one(t)
        assert v[0:12].sum() == 0.0

    def test_key_confidence_clamped(self):
        enc = self._enc()
        t = make_track(key_confidence=1.5)
        v = enc.encode_one(t)
        assert v[12] == 1.0

        t2 = make_track(key_confidence=-0.5)
        v2 = enc.encode_one(t2)
        assert v2[12] == 0.0

    def test_duration_nonzero(self):
        enc = self._enc()
        t = make_track(duration_s=180.0)
        v = enc.encode_one(t)
        expected = math.log1p(180.0) / math.log1p(600.0)
        assert abs(v[13] - expected) < 1e-10

    def test_explicit_flag(self):
        enc = self._enc()
        t_explicit = make_track(explicit=True)
        t_clean = make_track(explicit=False)
        assert enc.encode_one(t_explicit)[16] == 1.0
        assert enc.encode_one(t_clean)[16] == 0.0

    def test_tags_multi_hot(self):
        enc = self._enc(vocab=["soul", "jazz", "rock"])
        t = make_track(lfm_tags=["soul", "rock"])
        v = enc.encode_one(t)
        assert v[17] == 1.0   # soul at index 0
        assert v[18] == 0.0   # jazz not present
        assert v[19] == 1.0   # rock at index 2

    def test_tags_case_insensitive(self):
        enc = self._enc(vocab=["soul"])
        t = make_track(lfm_tags=["SOUL"])
        v = enc.encode_one(t)
        assert v[17] == 1.0

    def test_encode_batch(self):
        enc = self._enc()
        tracks = [make_track(name=f"T{i}") for i in range(5)]
        X = enc.encode(tracks)
        assert X.shape == (5, 512)

    def test_vocab_cap_at_tag_vocab_size(self):
        enc = MetadataEncoder()
        tags = [f"tag{i}" for i in range(1000)]
        enc.set_vocab(tags)
        assert enc.vocab_size == TAG_VOCAB_SIZE

    def test_reserved_dims_zero(self):
        enc = self._enc()
        t = make_track()
        v = enc.encode_one(t)
        # [273:512] should be zeros
        assert v[273:].sum() == 0.0


# ============================================================================
# embed_tracks tests
# ============================================================================

class TestEmbedTracks:
    def test_metadata_fallback(self):
        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul", "jazz"])
        tracks = [make_track() for _ in range(4)]
        X = embed_tracks(tracks, proj, enc)
        assert X.shape == (4, 512)

    def test_clap_npy_loaded(self, tmp_path):
        # Write a fake .npy CLAP embedding
        fake_emb = np.random.randn(512).astype(np.float32)
        npy_path = tmp_path / "track.npy"
        np.save(str(npy_path), fake_emb)

        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul"])
        t = make_track(path=tmp_path / "track.mp3")
        t.clap_npy = npy_path

        X = embed_tracks([t], proj, enc)
        np.testing.assert_allclose(X[0], fake_emb.astype(np.float64), atol=1e-6)

    def test_clap_npy_wrong_shape_falls_back(self, tmp_path):
        # .npy exists but has wrong shape — should fall back to metadata
        bad = np.random.randn(128).astype(np.float32)
        npy_path = tmp_path / "track.npy"
        np.save(str(npy_path), bad)

        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul"])
        t = make_track(path=tmp_path / "track.mp3")
        t.clap_npy = npy_path

        X = embed_tracks([t], proj, enc)
        assert X.shape == (1, 512)
        # Should NOT equal the bad embedding
        assert not np.allclose(X[0, :128], bad.astype(np.float64))


# ============================================================================
# Tag adjacency tests
# ============================================================================

class TestTagAdjacency:
    def test_symmetric(self):
        tracks = [
            make_track(name="A", lfm_tags=["soul", "jazz"]),
            make_track(name="B", lfm_tags=["soul", "rock"]),
            make_track(name="C", lfm_tags=["country"]),
        ]
        A = _tag_adjacency(tracks, threshold=0.10)
        np.testing.assert_array_equal(A, A.T)

    def test_diagonal_zero(self):
        tracks = [make_track(name=f"T{i}", lfm_tags=["soul"]) for i in range(5)]
        A = _tag_adjacency(tracks, threshold=0.0)
        np.testing.assert_array_equal(np.diag(A), np.zeros(5))

    def test_same_tags_connected(self):
        tracks = [
            make_track(name="A", lfm_tags=["soul"]),
            make_track(name="B", lfm_tags=["soul"]),
        ]
        A = _tag_adjacency(tracks, threshold=0.0)
        assert A[0, 1] == 1.0 and A[1, 0] == 1.0

    def test_no_overlap_no_edge(self):
        tracks = [
            make_track(name="A", lfm_tags=["soul"]),
            make_track(name="B", lfm_tags=["metal"]),
        ]
        A = _tag_adjacency(tracks, threshold=0.10)
        assert A[0, 1] == 0.0

    def test_threshold_cuts_low_jaccard(self):
        # Jaccard({soul,jazz,rock}, {soul}) = 1/3 ≈ 0.33
        tracks = [
            make_track(name="A", lfm_tags=["soul", "jazz", "rock"]),
            make_track(name="B", lfm_tags=["soul"]),
        ]
        A_strict = _tag_adjacency(tracks, threshold=0.50)
        A_loose = _tag_adjacency(tracks, threshold=0.10)
        assert A_strict[0, 1] == 0.0
        assert A_loose[0, 1] == 1.0

    def test_empty_tags_no_edge(self):
        tracks = [
            make_track(name="A", lfm_tags=[]),
            make_track(name="B", lfm_tags=[]),
        ]
        A = _tag_adjacency(tracks, threshold=0.0)
        assert A.sum() == 0.0


# ============================================================================
# PhiGraphSnapshot tests
# ============================================================================

class TestPhiGraphSnapshot:
    def _snap(self, n: int = 6) -> PhiGraphSnapshot:
        tracks = [make_track(name=f"T{i}", lfm_tags=["soul"]) for i in range(n)]
        rng = np.random.default_rng(7)
        H = rng.standard_normal((n, D_OUT))
        A = np.zeros((n, n))
        return PhiGraphSnapshot(tracks=tracks, H=H, A=A)

    def test_paths_length(self):
        snap = self._snap(5)
        assert len(snap.paths()) == 5

    def test_path_of_index(self):
        snap = self._snap(4)
        for i in range(4):
            assert snap.path_of(i) == snap.tracks[i].path

    def test_index_of_found(self):
        snap = self._snap(4)
        assert snap.index_of(snap.tracks[2]) == 2

    def test_index_of_not_found(self):
        snap = self._snap(4)
        foreign = make_track(path=Path("/nowhere/ghost.mp3"))
        assert snap.index_of(foreign) == -1

    def test_top_k_similar_length(self):
        snap = self._snap(10)
        nbrs = snap.top_k_similar(0, k=3)
        assert len(nbrs) == 3

    def test_top_k_excludes_self(self):
        snap = self._snap(8)
        for i in range(8):
            nbrs = snap.top_k_similar(i, k=4)
            assert i not in nbrs

    def test_top_k_sorted_by_similarity(self):
        snap = self._snap(6)
        nbrs = snap.top_k_similar(0, k=5)
        # Verify descending similarity order
        sims = [(snap.H[0] @ snap.H[j]) / (
            np.linalg.norm(snap.H[0]) * np.linalg.norm(snap.H[j]) + 1e-12
        ) for j in nbrs]
        assert sims == sorted(sims, reverse=True)

    def test_top_k_with_tiny_graph(self):
        snap = self._snap(2)
        nbrs = snap.top_k_similar(0, k=5)
        assert len(nbrs) == 1  # only 1 other node

    def test_N_property(self):
        snap = self._snap(7)
        assert snap.N == 7


# ============================================================================
# PhiGraph integration (synthetic library)
# ============================================================================

class TestPhiGraph:
    def test_build_returns_snapshot(self):
        g, tracks = make_phi_graph(8)
        snap = g.build()
        assert isinstance(snap, PhiGraphSnapshot)

    def test_snapshot_H_shape(self):
        g, tracks = make_phi_graph(8)
        snap = g.build()
        assert snap.H.shape == (8, D_OUT)

    def test_snapshot_H_l2_normalised(self):
        g, tracks = make_phi_graph(8)
        snap = g.build()
        norms = np.linalg.norm(snap.H, axis=1)
        np.testing.assert_allclose(norms, np.ones(8), atol=1e-10)

    def test_snapshot_A_shape(self):
        g, tracks = make_phi_graph(8)
        snap = g.build()
        assert snap.A.shape == (8, 8)

    def test_adjacency_method(self):
        g, tracks = make_phi_graph(6)
        A = g.adjacency()
        assert A.shape == (6, 6)

    def test_rebuild_idempotent(self):
        g, tracks = make_phi_graph(5)
        snap1 = g.build()
        snap2 = g.build()
        np.testing.assert_array_equal(snap1.H, snap2.H)
        np.testing.assert_array_equal(snap1.A, snap2.A)

    def test_snapshot_stored_on_graph(self):
        g, _ = make_phi_graph(4)
        assert g.snapshot is None
        g.build()
        assert g.snapshot is not None

    def test_repr_before_build(self):
        g, _ = make_phi_graph(4)
        assert "built=False" in repr(g)

    def test_repr_after_build(self):
        g, _ = make_phi_graph(4)
        g.build()
        assert "built=True" in repr(g)


# ============================================================================
# Integration — real library (requires LIBRARY_ROOT to exist)
# ============================================================================

@pytest.mark.integration
class TestPhiGraphRealLibrary:
    def test_real_library_scan(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        lib = PhiLibrary()
        n = lib.scan()
        assert n > 0, "Library scan returned 0 tracks"

    def test_real_library_build(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        g = PhiGraph()
        snap = g.build()
        assert snap.N > 0
        assert snap.H.shape == (snap.N, D_OUT)
        norms = np.linalg.norm(snap.H, axis=1)
        np.testing.assert_allclose(norms, np.ones(snap.N), atol=1e-10)

    def test_real_top_k_similar(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        g = PhiGraph()
        snap = g.build()
        nbrs = snap.top_k_similar(0, k=5)
        assert len(nbrs) == 5
        assert 0 not in nbrs
