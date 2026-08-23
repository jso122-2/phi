---
hub: VAULT
shard: 6
basin: 13.72
tags: [hub, music, vault]
---

# VAULT

#hub

Hub shard 6 — Obsidian PSSPPS retrieval signal.

Injected by `inject("VAULT", retrieval_confidence)` where retrieval_confidence
is the output of `vault_context._signal(result)` — the collapsed [0, 1] score
from the PSSPPS pipeline run on the current track title + artist.

When VAULT activates above threshold, `active_spoke_queries()` includes a
vault-retrieval query in its output, which triggers a secondary PSSPPS pass
for deeper context.

## Spoke context

Notes linked here describe retrieval infrastructure: the PSSPPS pipeline,
TF-IDF retrieval, harmonic perspective scoring, and pre/post-routing logic.

## Links

- [[psspps]] — the retrieval pipeline
- [[harmonic-index]] — ring state drives perspective_alpha
- [[TOPOLOGY]] — graph quality determines retrieval confidence
- [[ARTIST]] — artist notes are the primary retrieval target

## Physics

Basin centre 13.72 = 7·α. Nearest neighbour of MEMORY (shard 7) — under
resonance propagation, a strong retrieval signal bleeds directly into
long-term memory, linking immediate context to historical patterns.
