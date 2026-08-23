# source / engine-mycelial.md

#doc #md

> path: source/engine-mycelial.md  
> ext: .md  

---

# engine/mycelial

#code #module #engine #code

> source_path: engine/mycelial.py  
> package: engine  
> module: engine/mycelial  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/mycelial`  
**Source:** `engine/mycelial.py`

MycelialNetwork — CAIRRN-aware soft edge activation for the Obsidian graph.

Biological model (from "Rationale: Mycelial Intelligence in DAWN"):
  - Notes are nodes (root tips / fungal junction points)
  - Samba GNN semantic scores are resting edge conductances
  - CAIRRN hub pipeline modulates activation along hyphae
  - harmonic_propagate diffuses activation N steps across the ring
  - Edges below threshold are dormant; above are lit (anastomosed)
  - C-layer: each hub's memory_decay applies every tick → hyphal dormancy

CAIRRN integration constants (from CAIRRN SKILL):
  κ = 0.15   harmonic coupling ≡ mycelial conductance constant
  α = 1.96   double-well attractor locations
  τ = 30     coherence half-life (steps)
  x* = −W(1) ≈ −0.5671   coherence fixed point

Pipeline layers:
  Layer 1 (Ana-Chi):  modulated = metric × gravity × (decay if rattling)
  Layer 2 (neg_exp):  shard = floor(e^χ × 8 / 14.44) clamped [0, 7]
  Layer 3 (coherence): coherence = exp(−steps / τ); < 0.50 → re-route HOME

## API

- `class HyphalEdge` — A single soft edge between two notes with live activation tracking.
- `class CAIRRNRun` — Record of one CAIRRN pipeline pass.
- `class SporeResult` — Result of a mycelial_spore injection.
- `class CAIRRNPipeline` — Three-layer CAIRRN modulation pipeline.
- `class MycelialNetwork` — CAIRRN-aware mycelial activation layer over the Obsidian knowledge graph.

## Internal imports

`engine.vault_writer`

---

## Semantic links

→ [[HOME]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[graph]]
→ [[logger]]
→ [[HOME]]

## Related notes

→ [[source/engine-mycelial-substrate]]
→ [[source/workers-cairrn-init]]
→ [[source/workers-cairrn-mycelial]]
→ [[source/graph-init]]

---

## Semantic links

→ [[engine-mycelial]]
→ [[engine-mycelial-substrate]]
→ [[workers-cairrn-mycelial]]
→ [[models-octopus-head]]
→ [[graph-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-substrate-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
