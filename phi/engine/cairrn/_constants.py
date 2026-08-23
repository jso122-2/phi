# -*- coding: utf-8 -*-
"""phi.engine.cairrn._constants — canonical physics and hub geometry for phi CAIRRN.

This is the single source of truth for all CAIRRN constants used in the phi
application.  Every other module in this package imports from here — nothing
is defined inline.

SHARD GEOMETRY
──────────────
Shards are assigned by the neg_exp formula:

    shard = floor(e^χ × N_SHARDS / SHARD_NORM)   clamped to [0, N_SHARDS−1]

This produces a strictly monotone map: higher χ → higher shard.  The five
phi hubs land at shards 0, 1, 2, 3, and 7.  Shards 4–6 are propagation
waveguides — they carry diffused activation from high-energy bursts (CLAP,
COMMANDS) into adjacent hubs via harmonic coupling.

Canonical shard assignment (φ-specific):
    shard 0  →  agent-context   χ=0.03   background ML writes
    shard 1  →  CODE            χ=0.99   active playback / ranker
    shard 2  →  HOME            χ=1.54   library topology
    shard 3  →  MATH            χ=1.96   embedding / similarity
    shard 4  →  (waveguide)     —        CLAP diffusion
    shard 5  →  (waveguide)     —        COMMANDS diffusion
    shard 6  →  (waveguide)     —        COMMANDS diffusion
    shard 7  →  COMMANDS        χ=2.67   enrichment / high-priority

NOTE: A second shard geometry exists in the MCP station-hub system (shards
0–7 evenly divided across five named hubs).  That system is entirely
independent of phi and is NOT used here.  Do not confuse the two.

HUB τ DERIVATION
────────────────
Each hub's coherence time constant is derived from its memory_decay:

    τ = −1 / log(decay)   →   coherence(t) = decay^t = exp(−t/τ)

This ties the coherence curve to the activation decay rate so both signals
share the same characteristic timescale.  The CAIRRN SKILL.md uses τ=30
as a simplified global constant; phi uses the per-hub derivation.

FIXED POINT
───────────
The neg_exp map f(x) = −eˣ is closed under differentiation.  Its fixed
point x* = −W(1) ≈ −0.5671 is used as the Euler coherence floor: a hub
whose coherence falls below |x*| is in critical degradation territory
(beyond the soft 0.50 floor where the reroute fires).

PROPAGATION
───────────
Ring diffusion: index[i] += κ × (index[i−1] + index[i+1]) − α × index[i]
    κ = 0.15   coupling constant  (mycelial conductance)
    α = 1.96   double-well attractor locations
    N = 8      shards in the ring
"""

import math
from typing import Dict

# ── Physics ────────────────────────────────────────────────────────────────────

KAPPA:       float = 0.15              # harmonic coupling constant
ALPHA:       float = 1.96              # double-well attractor (= basins α·k for k=1)
N_SHARDS:    int   = 8                 # shards in the harmonic ring
SHARD_NORM:  float = 14.44             # normalisation constant for neg_exp shard map
                                       # = e^χ_max × N_SHARDS / max_shard_before_clamp
COHERENCE_FLOOR: float = 0.50          # soft floor — reroute fires below this
EULER_FLOOR:     float = 0.5671432904097838   # |x*| = |−W(1)| — hard Euler floor

# D friction gate — suppresses should_act when local friction delta is too high.
# D = |fl − (Ti · |x/Z| + βt)|
#   fl = LOCAL_FRICTION   baseline friction scalar
#   Ti = propagation steps for this RequestKind (from PROPAGATE_STEPS)
#   x  = modulated (Layer 1 output — normalised metric)
#   Z  = |z_awareness| (SCOP proxy; guarded ≥ Z_FLOOR to avoid division)
#   βt = coherence (SHI / pressure proxy)
# When D > D_GATE_THRESHOLD the friction is unbalanced → gate suppresses action.
LOCAL_FRICTION:    float = 0.5   # calibrated baseline local friction (fl)
D_GATE_THRESHOLD:  float = 1.0   # D ≤ threshold → action allowed (lower = stricter)
_Z_FLOOR:          float = 0.01  # minimum |z_awareness| to prevent divide-by-zero

# ── Hub definitions ────────────────────────────────────────────────────────────

#  tau = −1 / log(decay)   — per-hub coherence time constant
#  shard = floor(e^χ × N_SHARDS / SHARD_NORM) clamped [0, N_SHARDS−1]
#
#  Basin types (from CAIRRN SKILL.md):
#    HOME          true_center   slow, stable, high-gravity anchor
#    MATH          white_peak    medium, embedding resonance space
#    CODE          mirror        fast, playback-context river
#    COMMANDS      escape        rapid, ephemeral action signals
#    agent-context boundary      persistent but low-gravity annotation domain

HUB_PARAMS: Dict[str, dict] = {
    "HOME": {
        "chi":      1.5414,
        "gravity":  3.00,
        "rattling": False,
        "decay":    0.98,
        "tau":      49.5,    # −1/log(0.98) — slow: catalogue topology is stable
        "shard":    2,       # floor(e^1.5414 × 8/14.44) = floor(2.588) = 2
        "basin":    "true_center",
        "doc":      "Library topology. High-gravity anchor. Slow coherence decay.",
    },
    "MATH": {
        "chi":      1.9600,
        "gravity":  2.00,
        "rattling": True,
        "decay":    0.95,
        "tau":      19.5,    # −1/log(0.95) — medium: embedding bursts decay in ~20 steps
        "shard":    3,       # floor(e^1.96 × 8/14.44) = floor(3.933) = 3
        "basin":    "white_peak",
        "doc":      "Embedding / similarity space. CLAP inference lands here.",
    },
    "CODE": {
        "chi":      0.9900,
        "gravity":  1.50,
        "rattling": True,
        "decay":    0.93,
        "tau":      13.8,    # −1/log(0.93) — fast: listening context refreshes often
        "shard":    1,       # floor(e^0.99 × 8/14.44) = floor(1.491) = 1
        "basin":    "mirror",
        "doc":      "Active playback context. Track transitions and poll ticks.",
    },
    "COMMANDS": {
        "chi":      2.6700,
        "gravity":  1.00,
        "rattling": True,
        "decay":    0.90,
        "tau":      9.5,     # −1/log(0.90) — very fast: enrichment queue pressure
        "shard":    7,       # floor(e^2.67 × 8/14.44) = floor(8.0) = 7 (clamped)
        "basin":    "escape",
        "doc":      "Enrichment dispatch and high-priority actions.",
    },
    "agent-context": {
        "chi":      0.0300,
        "gravity":  0.50,
        "rattling": False,
        "decay":    0.90,
        "tau":      9.5,     # −1/log(0.90) — fast: agent write activity
        "shard":    0,       # floor(e^0.03 × 8/14.44) = floor(0.571) = 0
        "basin":    "boundary",
        "doc":      "Background ML writes. BPM / mood / annotation domain.",
    },
}

# Ordered by shard (ascending) — canonical hub ordering on the ring
HUB_ORDER: tuple = ("agent-context", "CODE", "HOME", "MATH", "COMMANDS")

# ── Shard → hub name (only the five occupied shards) ─────────────────────────

SHARD_HUB: Dict[int, str] = {
    params["shard"]: name
    for name, params in HUB_PARAMS.items()
}
# {0: "agent-context", 1: "CODE", 2: "HOME", 3: "MATH", 7: "COMMANDS"}

# ── Priority tiers (shard → urgency tier 0–3) ────────────────────────────────

def shard_priority(shard: int) -> int:
    """
    Map shard [0–7] to priority tier [0–3]. Higher = more urgent.

    Tier assignment:
        0  DEFER   — shard 0   (agent-context — background annotations)
        1  NORMAL  — shards 1–3 (CODE, HOME, MATH — active session work)
        2  HIGH    — shards 4–6 (waveguide propagation — uncommitted work)
        3  URGENT  — shard 7   (COMMANDS — enrichment, action queue)
    """
    if shard >= 7:
        return 3    # URGENT — COMMANDS
    if shard >= 4:
        return 2    # HIGH — waveguide shards
    if shard >= 1:
        return 1    # NORMAL — CODE (1), HOME (2), MATH (3)
    return 0        # DEFER — agent-context (0)

PRIORITY_LABELS: tuple = ("DEFER", "NORMAL", "HIGH", "URGENT")

# ── Page → hub mapping (pages are trees, floor is CAIRRN) ─────────────────────

PAGE_HUB: Dict[str, str] = {
    "playing":  "CODE",      # shard 1 — playback context / ranker
    "library":  "HOME",      # shard 2 — catalogue topology
    "genre":    "MATH",      # shard 3 — similarity / CLAP embedding space
    "playlist": "CODE",      # shard 1 — queue context (same root as playing)
    "mixer":    "COMMANDS",  # shard 7 — audio control / high-priority
}

# ── Propagation steps per RequestKind ─────────────────────────────────────────
# Defined here as a dict of string → int (RequestKind imported later to avoid
# circular imports; the router uses these by value).

PROPAGATE_STEPS: Dict[str, int] = {
    "POLL_TICK":         1,   # 1.5 s heartbeat — minimal diffusion
    "PAGE_NAV":          2,   # page switch — moderate diffusion
    "TRACK_TRANSITION":  1,   # track change — local diffusion
    "ML_INFERENCE":      3,   # background annotation — wide diffusion so results reach MATH (shard 3)
    "CLAP_INFERENCE":    3,   # CLAP burst — wide diffusion across the ring
    "SIMILARITY_SEARCH": 2,   # search — moderate
    "ENRICH_DISPATCH":   1,   # enrichment — local
    "SKIP_EVENT":        2,   # skip — diffuses into HOME + agent-context
    "RIDER_ACTION":      2,   # direct button press — Rider steering impulse
    "PLAYLIST_BUILD":    3,   # batch playlist build — wide MATH diffusion (same as CLAP)
}

# ── Rider key → hub routing ───────────────────────────────────────────────────
# Each Jim action maps to a (hub, metric) pair.  The hub is the CAIRRN home
# that semantically owns that class of action; the metric is the normalised
# steering pressure [0, 1] it injects into the harmonic ring.
#
# Semantic grouping:
#   CODE      — transport: direct playback control, the Rider's hand on the wheel
#   COMMANDS  — mode toggles: rapid, ephemeral state changes
#   HOME      — navigation: cursor moves through the UI topology
#   agent-context — meta: looking inward (help, palette, analysis views)

ACTION_CAIRRN: Dict[str, tuple] = {
    # Transport — CODE (mirror basin, fast context, shard 1)
    "prev":       ("CODE",          0.70),  # hard backward skip — strong Rider signal
    "next":       ("CODE",          0.70),  # hard forward skip — strong Rider signal
    "play_pause": ("CODE",          0.50),  # toggle playback — clear intent
    "seek_fwd":   ("CODE",          0.15),  # gentle nudge forward — low pressure
    "seek_back":  ("CODE",          0.15),  # gentle nudge back — low pressure
    "vol_up":     ("CODE",          0.10),  # fine adjustment — minimal pressure
    "vol_down":   ("CODE",          0.10),  # fine adjustment — minimal pressure
    # Mode commands — COMMANDS (escape basin, very fast, shard 7)
    "mute":       ("COMMANDS",      0.40),  # mode toggle — binary, decisive
    "shuffle":    ("COMMANDS",      0.50),  # mode toggle — restructures the queue
    "repeat":     ("COMMANDS",      0.40),  # mode toggle — changes loop contract
    "sleep":      ("COMMANDS",      0.30),  # timed command — deferred action
    # Navigation — HOME (true_center basin, slow stable, shard 2)
    "rooms":      ("HOME",          1.00),  # explicit topology switch — max pressure
    "deselect":   ("HOME",          0.20),  # cursor clear — mild reset
    "escape":     ("HOME",          0.20),  # dismiss — navigation reset
    "sidebar":    ("HOME",          0.25),  # layout shift — UI topology
    "fullscreen": ("HOME",          0.20),  # display mode shift
    # Meta / context — agent-context (boundary basin, low gravity, shard 0)
    "help":             ("agent-context", 0.30),  # Rider inspecting the map
    "overlay":          ("agent-context", 0.40),  # command palette — meta intent
    # Depth navigation — HOME (topology shift) or agent-context (ML layer)
    "navigate_deeper":  ("HOME",          1.00),  # default; overridden per call
    # Z-spine — agent-context (boundary basin: new space not yet mapped)
    "toggle_z_spine":   ("agent-context", 0.60),  # crossing into unmapped territory
}


# ── Validation ────────────────────────────────────────────────────────────────

def _validate() -> None:
    """Sanity-check that the hub shard values match the formula at import time."""
    for name, p in HUB_PARAMS.items():
        expected = min(N_SHARDS - 1, int(math.exp(p["chi"]) * N_SHARDS / SHARD_NORM))
        assert p["shard"] == expected, (
            f"HUB_PARAMS['{name}'] shard={p['shard']} but formula gives {expected}"
        )

_validate()
