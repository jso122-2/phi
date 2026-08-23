# source / engine-cairrn-bridge.md

#doc #md

> path: source/engine-cairrn-bridge.md  
> ext: .md  

---

# engine/cairrn_bridge

#code #module #engine #code

> source_path: engine/cairrn_bridge.py  
> package: engine  
> module: engine/cairrn_bridge  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/cairrn_bridge`  
**Source:** `engine/cairrn_bridge.py`

CairnBridge — local CAIRRN state machine for OctopusTracer autonomy.

Implements the full CAIRRN three-layer modulation pipeline locally, without
any external MCP calls. The bridge:

    1. Maintains hub activation state across cycles
    2. Runs each vault metric through Ana-Chi → neg_exp sharding → coherence
    3. Exposes per-hub coherence scores to the TracerDaemon as spawn signals
    4. Propagates activation through the harmonic ring on each tick

Hub geometry (from CAIRRN SKILL.md):
    HOME          χ=1.5414  gravity=3.00  rattling=no   decay=0.98
    MATH          χ=1.9600  gravity=2.00  rattling=yes  decay=0.95
    CODE          χ=0.9900  gravity=1.50  rattling=yes  decay=0.93
    COMMANDS      χ=2.6700  gravity=1.00  rattling=yes  decay=0.90
    agent-context χ=0.0300  gravity=0.50  rattling=no   decay=0.90

Shard mapping (neg_exp):
    shard = floor(e^χ × 8 / 14.44)  clamped to [0, 7]

Coherence (Layer 3):
    coherence = exp(−steps / τ_hub)  — per-hub time constant
    τ_hub derived from memory_decay: τ = -1 / log(decay)
        HOME          τ ≈ 49.5   (slow — graph topology is stable)
        MATH          τ ≈ 19.5   (medium)
        CODE          τ ≈ 13.8   (medium-fast)
        COMMANDS      τ ≈  9.5   (fast — actionable signals)
        agent-context τ ≈  9.5   (fast — agent write activity)
    fixed point x* = −W(1) ≈ −0.5671432904097838
    if coherence < 0.50 → hub flagged incoherent → route to HOME

Harmonic propagation:
    κ = 0.15  (coupling constant)
    α = 1.96  (double-well attractor locations)
    Each propagation step: index[i] += κ × (index[i-1] + index[i+1]) − α × index[i]

Usage from TracerDaemon:
    bridge = CairnBridge()
    bridge.step("CODE", metric

---

## Semantic links

→ [[engine-cairrn-bridge]]
→ [[engine-bridge-factory]]
→ [[engine-init]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-bridge-factory-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-bridge-factory-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
