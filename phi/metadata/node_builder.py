"""phi.metadata.node_builder — assemble a 6-node SongNode window.

Public API
----------
    nodes = build_window(tracks)
        list[Track] (≤6) → list[SongNode]
        Runs librosa extraction on each track's audio path.
        Assigns node_id (0–5) and CAIRRN shard from _SHARD_MAP.
        degree is 0 at build time — populated by the adjacency layer.

    nodes = build_window(tracks, extract_audio=False)
        Skip librosa extraction; AudioFeatures zeroed.
        Useful for testing or when audio files are not yet available.
"""
from __future__ import annotations

from phi._track import Track
from phi.metadata.extractor import extract_or_zero
from phi.metadata.schema import (
    AudioFeatures,
    GraphPosition,
    SongNode,
    WINDOW_SIZE,
    _SHARD_MAP,
)

__all__ = ["build_window"]


def build_window(
    tracks: list[Track],
    extract_audio: bool = True,
) -> list[SongNode]:
    """Build a 6-node SongNode window from a list of Tracks.

    Parameters
    ----------
    tracks        : up to WINDOW_SIZE (6) Track objects
    extract_audio : if True, run librosa extraction on each track's audio path;
                    if False, AudioFeatures is zeroed (fast, for testing)

    Returns
    -------
    list[SongNode]
        One SongNode per track, node_id assigned by position in *tracks*.
        degree defaults to 0 — callers should update after adjacency is built.

    Raises
    ------
    ValueError if len(tracks) > WINDOW_SIZE
    """
    if len(tracks) > WINDOW_SIZE:
        raise ValueError(
            f"Window size is fixed at {WINDOW_SIZE}; got {len(tracks)} tracks."
        )

    nodes: list[SongNode] = []
    for node_id, track in enumerate(tracks):
        audio = extract_or_zero(track.path) if extract_audio else AudioFeatures()
        shard = _SHARD_MAP[node_id]
        position = GraphPosition(node_id=node_id, shard=shard)
        nodes.append(SongNode(track=track, audio=audio, position=position))

    return nodes


def update_degrees(nodes: list[SongNode], A: "np.ndarray") -> None:  # type: ignore[name-defined]
    """Write degree (row-sum of A) into each node's GraphPosition in-place.

    Call after adjacency is built:
        A = _tag_adjacency(tracks, threshold)
        update_degrees(nodes, A)

    Parameters
    ----------
    nodes : list[SongNode] as returned by build_window
    A     : (N, N) binary adjacency, N == len(nodes)
    """
    import numpy as np
    degrees = np.asarray(A).sum(axis=1).astype(int).tolist()
    for node, deg in zip(nodes, degrees):
        node.position.degree = int(deg)
