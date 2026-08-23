---
title: "CLAPProjection and PhiGraph — DAWN bridge layer"
created: 2026-07-17T01:33:09.223174+00:00
zone: agent-log
tags: [agent-log]
---
# CLAPProjection and PhiGraph — DAWN bridge layer

CLAPProjection (phi/models/clap_proj.py) is a single nn.Linear(512, 256) with LayerNorm pre-conditioning and L2-normalised output. It bridges CLAP's 512-d audio embedding space into SambaGNN's 256-d node embedding space. The architectural justification: CLAP is itself a contrastive language-audio model, so its audio vectors are already geometrically aligned to language embeddings — a linear rotation/scale is sufficient, no non-linear transform required.

PhiGraph (phi/graph/phi_graph.py) wraps a Phi Library and a CLAPProjection to produce H ∈ ℝ^(N_tracks × 256), the direct input for OctopusTracer. It mirrors the TopologicalGraph contract: build() is safe to call repeatedly, adjacency() is on-demand (soft_edge_mode doesn't need it), and PhiGraphSnapshot carries paths[], index_of(), path_of(), and top_k_similar() for round-tripping OctopusTracer arm outputs back to track paths.

The SproutArm output over H is the 'claw that breathes DAWN life': high sprout score at node u means the track u's neighbourhood in the embedding space is structurally underrepresented — a gap in the library's genre/mood topology that the system can surface as a search target.

## Related Notes

---

## Auto-linked

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[sessions]]
→ [[2026-07-17T02-58-58Z-RsyncBridge — real-time Cursor to Obsidian graph sync]]
→ [[logger]]

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[git-log]]
→ [[graph]]
→ [[2026-07-13-040738-2026-07-13t14-07-38-557-10-00]]
→ [[README]]

→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[graph-logger]]
→ [[HOME]]
→ [[graph-init]]
→ [[CODE]]
→ [[attractors]]
