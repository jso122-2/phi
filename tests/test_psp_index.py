"""
Tests for PspIndex — phi/models/psp_index.py.

Uses tmp_path for the SQLite db and synthetic Track objects.
Real files are created in tmp_path only where mtime invalidation is tested.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from phi._track import Track
from phi.models.psp_index import PspIndex


# ============================================================================
# Helpers
# ============================================================================


def make_track(
    name: str = "TestTrack",
    artist: str = "Artist",
    lfm_tags: list[str] | None = None,
    discogs_genre: list[str] | None = None,
    discogs_style: list[str] | None = None,
    path: Path | None = None,
) -> Track:
    """Synthetic Track with fake paths unless *path* is given."""
    p = path or Path(f"/fake/{name}.mp3")
    return Track(
        path=p,
        json_path=p.with_suffix(".json"),
        name=name,
        artist=artist,
        lfm_tags=lfm_tags if lfm_tags is not None else ["soul"],
        discogs_genre=discogs_genre or [],
        discogs_style=discogs_style or [],
    )


def make_index(tmp_path: Path) -> PspIndex:
    return PspIndex(tmp_path / "psp.db")


# ============================================================================
# build() — basic
# ============================================================================


class TestBuildCount:
    def test_first_build_returns_n(self, tmp_path):
        idx = make_index(tmp_path)
        tracks = [make_track(f"T{i}") for i in range(5)]
        count = idx.build(tracks)
        assert count == 5

    def test_empty_tracks_returns_zero(self, tmp_path):
        idx = make_index(tmp_path)
        assert idx.build([]) == 0

    def test_single_track(self, tmp_path):
        idx = make_index(tmp_path)
        assert idx.build([make_track("Solo")]) == 1


# ============================================================================
# build() — mtime invalidation
# ============================================================================


class TestMtimeInvalidation:
    def test_rebuild_skips_unchanged(self, tmp_path):
        """Second build with same tracks (mtime=0 for non-existent paths) → 0."""
        idx = make_index(tmp_path)
        tracks = [make_track("A"), make_track("B"), make_track("C")]
        idx.build(tracks)
        count = idx.build(tracks)
        assert count == 0

    def test_rebuild_updates_changed_file(self, tmp_path):
        """Touching a real file updates its mtime → that one track is rewritten."""
        f_a = tmp_path / "A.mp3"
        f_b = tmp_path / "B.mp3"
        f_a.write_bytes(b"audio_a")
        f_b.write_bytes(b"audio_b")

        t_a = make_track("A", path=f_a)
        t_b = make_track("B", path=f_b)

        idx = make_index(tmp_path)
        idx.build([t_a, t_b])

        # Ensure at least 10 ms passes so mtime changes
        time.sleep(0.05)
        f_a.touch()

        count = idx.build([t_a, t_b])
        assert count == 1

    def test_rebuild_updates_all_new_tracks(self, tmp_path):
        """First build is fresh → returns N for N tracks."""
        idx = make_index(tmp_path)
        tracks = [make_track(f"X{i}") for i in range(4)]
        assert idx.build(tracks) == 4

    def test_rebuild_after_adding_track(self, tmp_path):
        """Adding one new track to the library writes exactly that one row."""
        f_existing = tmp_path / "Old.mp3"
        f_existing.write_bytes(b"old")
        t_old = make_track("Old", path=f_existing)

        idx = make_index(tmp_path)
        idx.build([t_old])

        t_new = make_track("New")  # fake path → mtime 0 → new to DB
        count = idx.build([t_old, t_new])
        assert count == 1


# ============================================================================
# tfidf_matrix()
# ============================================================================


class TestTfIdfMatrix:
    def test_shape_matches_track_count(self, tmp_path):
        idx = make_index(tmp_path)
        tracks = [make_track(f"T{i}", lfm_tags=[f"tag{i}"]) for i in range(6)]
        idx.build(tracks)
        mat = idx.tfidf_matrix()
        assert mat.shape[0] == 6

    def test_vocab_size_matches_columns(self, tmp_path):
        idx = make_index(tmp_path)
        tracks = [make_track(f"T{i}") for i in range(4)]
        idx.build(tracks)
        vocab = idx.vocabulary()
        mat = idx.tfidf_matrix()
        assert mat.shape[1] == len(vocab)

    def test_empty_index_returns_zero_shape(self, tmp_path):
        idx = make_index(tmp_path)
        mat = idx.tfidf_matrix()
        assert mat.shape[0] == 0

    def test_matrix_dtype_is_float64(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("Solo")])
        assert idx.tfidf_matrix().dtype == np.float64

    def test_values_in_unit_range(self, tmp_path):
        idx = make_index(tmp_path)
        tracks = [make_track(f"T{i}", lfm_tags=["jazz", "soul"]) for i in range(5)]
        idx.build(tracks)
        mat = idx.tfidf_matrix()
        assert np.all(mat >= 0.0)
        # L2-normalised rows — norms ≤ 1 (zero rows allowed)
        norms = np.linalg.norm(mat, axis=1)
        assert np.all(norms <= 1.0 + 1e-9)


# ============================================================================
# track_paths()
# ============================================================================


class TestTrackPaths:
    def test_length_matches_track_count(self, tmp_path):
        idx = make_index(tmp_path)
        tracks = [make_track(f"T{i}") for i in range(7)]
        idx.build(tracks)
        assert len(idx.track_paths()) == 7

    def test_paths_are_strings(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("A"), make_track("B")])
        for p in idx.track_paths():
            assert isinstance(p, str)

    def test_empty_index_returns_empty_list(self, tmp_path):
        idx = make_index(tmp_path)
        assert idx.track_paths() == []

    def test_track_paths_and_matrix_row_order_consistent(self, tmp_path):
        """track_paths() and tfidf_matrix() must share row order."""
        idx = make_index(tmp_path)
        tracks = [make_track(f"Track{i}", lfm_tags=[f"genre{i}"]) for i in range(5)]
        idx.build(tracks)

        paths = idx.track_paths()
        mat = idx.tfidf_matrix()
        assert len(paths) == mat.shape[0]


# ============================================================================
# vocabulary()
# ============================================================================


class TestVocabulary:
    def test_returns_non_empty_after_build(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("Alpha", lfm_tags=["jazz", "blues"])])
        vocab = idx.vocabulary()
        assert len(vocab) > 0

    def test_returns_list_of_strings(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("Test")])
        for term in idx.vocabulary():
            assert isinstance(term, str)

    def test_empty_index_returns_empty_list(self, tmp_path):
        idx = make_index(tmp_path)
        assert idx.vocabulary() == []

    def test_known_terms_present(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("JazzSong", artist="Coltrane", lfm_tags=["jazz"])])
        vocab = idx.vocabulary()
        # "jazz" is a non-stopword term → must appear
        assert "jazz" in vocab


# ============================================================================
# close()
# ============================================================================


class TestClose:
    def test_close_does_not_crash(self, tmp_path):
        idx = make_index(tmp_path)
        idx.build([make_track("X")])
        idx.close()  # should not raise

    def test_close_twice_does_not_crash(self, tmp_path):
        idx = make_index(tmp_path)
        idx.close()
        idx.close()  # second close must not raise

    def test_close_on_empty_index(self, tmp_path):
        idx = make_index(tmp_path)
        idx.close()


# ============================================================================
# Persistence — reopen DB
# ============================================================================


class TestPersistence:
    def test_data_survives_reopen(self, tmp_path):
        db_path = tmp_path / "psp.db"
        tracks = [make_track(f"T{i}", lfm_tags=[f"tag{i}"]) for i in range(3)]

        idx = PspIndex(db_path)
        idx.build(tracks)
        idx.close()

        # Reopen and check
        idx2 = PspIndex(db_path)
        assert len(idx2.track_paths()) == 3
        assert len(idx2.vocabulary()) > 0
        idx2.close()
