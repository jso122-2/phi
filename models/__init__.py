"""
OctopusTracer models package.

Canonical entry point:

    from models import OctopusAttentionHead
    from models import BERTClipper, SSMCore, OctopusArms, SuckerPool
    from models import compute_R
    from models import GenrePredictor   # lazy — requires xgboost + cluster_out/
    from models import SambaGNN         # lazy — lives in phi.gnn; requires torch
"""

from models.bert_clipper import BERTClipper
from models.octopus_head import OctopusAttentionHead, FS_MAX_EXCLUSIVE
from models.ssm import SSMCore
from models.regression import (
    complement_graph,
    scup_cosine,
    angular_dist,
    complement_laplacian,
    tangent_flow,
    regression_matrix,
    compute_R,
)
from models.arms import MLPArm, OctopusArms, ArmScores, ARM_NAMES
from models.suckers import LoRASucker, SuckerPool, SpawnEvent

__all__ = [
    "BERTClipper",
    "OctopusAttentionHead",
    "FS_MAX_EXCLUSIVE",
    "SSMCore",
    "complement_graph",
    "scup_cosine",
    "angular_dist",
    "complement_laplacian",
    "tangent_flow",
    "regression_matrix",
    "compute_R",
    "MLPArm",
    "OctopusArms",
    "ArmScores",
    "ARM_NAMES",
    "LoRASucker",
    "SuckerPool",
    "SpawnEvent",
    "GenrePredictor",
    "SambaGNN",
]


def __getattr__(name: str):
    """Lazy optional surfaces — keep the numpy package importable without xgboost/torch."""
    if name == "GenrePredictor":
        from models.genre_predictor import GenrePredictor
        return GenrePredictor
    if name == "SambaGNN":
        from phi.gnn.samba_gnn import SambaGNN
        return SambaGNN
    raise AttributeError(f"module 'models' has no attribute {name!r}")
