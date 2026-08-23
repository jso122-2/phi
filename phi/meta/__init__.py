# -*- coding: utf-8 -*-
"""phi.meta — tag reading, enrichment pipeline, cover art, lyrics, and cache."""
from phi.meta.reader       import read_meta, scan_folder, track_sort_key
from phi.meta.art          import make_photo, art_to_ascii, art_to_ascii_colored
from phi.meta.consensus    import (
    bpm_consensus,
    buoyancy_score,
    build_consensus_track,
    ConsensusTrack,
    genre_consensus,
    meta_score,
)
from phi.meta.enricher     import EnrichResult, enrich_track
from phi.meta.review_queue import ReviewItem, ReviewQueue, ReviewStatus
from phi.meta.dedup        import DupGroup, find_duplicates, find_tag_duplicates
from phi.meta.lyrics       import get_lyrics
from phi.meta.cache        import MetaCache
from phi.meta._octopus_types import (
    EnrichJob,
    OrganizationPlan,
    TAG_VOCAB,
    MERGE_THRESHOLD,
    GRAFT_THRESHOLD,
    TAG_THRESHOLD,
    PRUNE_WARNING,
)
try:
    from phi.meta._meta_embedder import MetaEmbedder
except ImportError:
    MetaEmbedder = None  # type: ignore[assignment,misc]

try:
    from phi.meta.octopus_organizer import OctopusOrganizer, make_organizer
except ImportError:
    OctopusOrganizer = None  # type: ignore[assignment,misc]
    make_organizer = None    # type: ignore[assignment]

try:
    from phi.meta.spotify_bulk_enrich import SpotifyBulkResult, run_bulk_enrich
except ImportError:
    SpotifyBulkResult = None  # type: ignore[assignment,misc]
    run_bulk_enrich = None    # type: ignore[assignment]

__all__ = [
    "read_meta", "scan_folder", "track_sort_key",
    "make_photo",
    "art_to_ascii",
    "art_to_ascii_colored",
    # Consensus spine
    "bpm_consensus",
    "buoyancy_score",
    "build_consensus_track",
    "ConsensusTrack",
    "genre_consensus",
    "meta_score",
    # Enrichment
    "EnrichResult", "enrich_track",
    "ReviewItem", "ReviewQueue", "ReviewStatus",
    "DupGroup", "find_duplicates", "find_tag_duplicates",
    "get_lyrics",
    "MetaCache",
    # Octopus-driven organisation
    "OctopusOrganizer",
    "OrganizationPlan",
    "EnrichJob",
    "MetaEmbedder",
    "TAG_VOCAB",
    "MERGE_THRESHOLD",
    "GRAFT_THRESHOLD",
    "TAG_THRESHOLD",
    "PRUNE_WARNING",
    "make_organizer",
    # Spotify bulk enrichment
    "SpotifyBulkResult",
    "run_bulk_enrich",
]
