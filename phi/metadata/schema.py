"""phi.metadata.schema — Three-layer song node schema.

Layer 1  Editorial  — sourced from phi._track.Track (ID3 + enrichment JSON)
Layer 2  Audio      — AudioFeatures, librosa-computed from local audio file
Layer 3  Graph      — GraphPosition, assigned at window build time

SongNode binds all three layers for a single track in a 6-node window.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from phi._track import Track

# Fixed window cardinality — matches the 6×6 complement adjacency input head.
WINDOW_SIZE: int = 6

# Number of CAIRRN shards (0–7).  Nodes 0–5 map to shards 0–5; shards 6–7 idle.
_SHARD_MAP: tuple[int, ...] = (0, 1, 2, 3, 4, 5)


# ---------------------------------------------------------------------------
# Layer 2 — Audio features
# ---------------------------------------------------------------------------

@dataclass
class AudioFeatures:
    """Librosa-computed numeric features for graph edge construction.

    All fields are scalars or fixed-length lists so the dataclass is
    JSON-serialisable without extra machinery.

    to_vector() flattens to (30,) float64 for adjacency / complement-Laplacian.

    Layout of to_vector():
        [0]     tempo             BPM
        [1]     loudness_db       mean RMS amplitude in dB
        [2]     zero_crossing_rate
        [3]     spectral_centroid Hz mean
        [4]     spectral_rolloff  Hz mean
        [5:17]  chroma_mean       12-d chroma energy per pitch class
        [17:30] mfcc_mean         13-d MFCC coefficients
    """
    tempo: float = 0.0
    loudness_db: float = 0.0
    zero_crossing_rate: float = 0.0
    spectral_centroid: float = 0.0
    spectral_rolloff: float = 0.0
    chroma_mean: list[float] = field(default_factory=lambda: [0.0] * 12)
    mfcc_mean: list[float] = field(default_factory=lambda: [0.0] * 13)

    def to_vector(self) -> np.ndarray:
        """Flatten all features to (30,) float64."""
        base = [
            self.tempo,
            self.loudness_db,
            self.zero_crossing_rate,
            self.spectral_centroid,
            self.spectral_rolloff,
        ]
        return np.array(base + self.chroma_mean + self.mfcc_mean, dtype=np.float64)

    def __post_init__(self) -> None:
        if len(self.chroma_mean) != 12:
            raise ValueError(f"chroma_mean must be length 12, got {len(self.chroma_mean)}")
        if len(self.mfcc_mean) != 13:
            raise ValueError(f"mfcc_mean must be length 13, got {len(self.mfcc_mean)}")


# ---------------------------------------------------------------------------
# Layer 3 — Graph position
# ---------------------------------------------------------------------------

@dataclass
class GraphPosition:
    """Window-scoped graph metadata for one node.

    node_id  : index within the 6-node window (0–5)
    degree   : row-sum of A after window adjacency is built (populated by
               node_builder after adjacency construction)
    shard    : CAIRRN shard assignment (0–7); derived from node_id via _SHARD_MAP
    h_u      : Phi embedding for this node — populated at inference time,
               zeroed at build time
    """
    node_id: int = 0
    degree: int = 0
    shard: int = 0
    h_u: list[float] = field(default_factory=lambda: [0.0] * 256)

    def __post_init__(self) -> None:
        if not (0 <= self.node_id < WINDOW_SIZE):
            raise ValueError(f"node_id must be 0–{WINDOW_SIZE - 1}, got {self.node_id}")
        if not (0 <= self.shard <= 7):
            raise ValueError(f"shard must be 0–7, got {self.shard}")
        if len(self.h_u) != 256:
            raise ValueError(f"h_u must be length 256, got {len(self.h_u)}")


# ---------------------------------------------------------------------------
# Composite node
# ---------------------------------------------------------------------------

@dataclass
class SongNode:
    """One song node in a 6-node window — all three schema layers.

    track    : Layer 1 — editorial metadata (Track dataclass)
    audio    : Layer 2 — librosa-computed audio features
    position : Layer 3 — graph window position + CAIRRN shard

    The full feature vector available to the regression pipeline is:
        H[node_id]  = position.h_u          (256-d Phi embedding, post-inference)
        a_u         = audio.to_vector()     (30-d numeric, for graph construction)
    """
    track: Track
    audio: AudioFeatures
    position: GraphPosition

    @property
    def node_id(self) -> int:
        return self.position.node_id

    @property
    def shard(self) -> int:
        return self.position.shard

    @property
    def display(self) -> str:
        return f"[{self.node_id}] {self.track.display_name}"

    def __repr__(self) -> str:
        return (
            f"<SongNode node_id={self.node_id} shard={self.shard} "
            f"track={self.track.display_name!r}>"
        )
