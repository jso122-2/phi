# source / engine-prefeed-shuffle.md

#doc #md

> path: source/engine-prefeed-shuffle.md  
> ext: .md  

---

# engine/prefeed_shuffle

#code #module #engine #code

> source_path: engine/prefeed_shuffle.py  
> package: engine  
> module: engine/prefeed_shuffle  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/prefeed_shuffle`  
**Source:** `engine/prefeed_shuffle.py`

CAIRRN-bound prefeed shuffle — double-buffer soft-queue for track ordering.

Architecture (Instagram analogy)
---------------------------------
Instagram pre-uploads a photo to its CDN while you're still editing it.
When you press "Share", the upload is already done — zero visible latency.

This module does the same for shuffle order:

    COHERENCE BUILDING          COHERENCE THRESHOLD CROSSED
    (gate closed)               (gate opens)
         │                              │
         ▼                              ▼
    prefeed()                      commit()
    compute next order          swap pending → active
    from CAIRRN state           cursor resets to 0
    store in _pending           _pending cleared

While coherence < threshold  →  serve tracks from _active (hysteresis)
When coherence ≥ threshold   →  commit: _pending becomes _active instantly

CAIRRN controls the order
--------------------------
The harmonic index shard activations (8 values) seed a "gravity vector" in
H-space (256-d).  Tracks are scored by their cosine similarity to this
gravity vector, then sorted with calibrated exploration noise.

    g = softmax(activations) @ Q          # (256,) gravity in H-space
    score[i] = H[i] · g + ε · noise[i]   # harmonic resonance + exploration
    order = argsort(-score)               # descending: most resonant first

Q ∈ ℝ^(8×256) is a fixed random orthonormal-ish projection (seed=42) that
maps the 8-shard space into H-space.  Fixed seed → same Q every run →
deterministic gravity for the same shard activations.

When all shard activations are equal → uniform g → exploration noise
dominates → effectively random shuffle.
When CODE shards (3, 4) are hot → track

---

## Semantic links

→ [[engine-prefeed-shuffle]]
→ [[mcp-server-tools-prefeed-shuffle]]
→ [[engine-phi-player]]
→ [[scripts-pretrain-loop]]
→ [[pipeline-worker-executor]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
