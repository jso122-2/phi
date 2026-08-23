---
hub: PLAYBACK
shard: 0
basin: 1.96
tags: [hub, music, playback]
---

# PLAYBACK

#hub

Hub shard 0 — live track state and queue context.

Activated on every track load (`inject("PLAYBACK", 1.0)`). The strongest and most
immediate signal in the ring — it bootstraps propagation across all other hubs.

## Spoke context

Notes linked here describe the current listening session: what is playing,
what is queued, and how the session has moved so far.

## Links

- [[ENERGY]] — playback drives energy context
-  — session history feeds back into playback decisions
- [[HOME]] — library topology anchor

## Signal routing

```
track load
    │
    ▼
inject("PLAYBACK", 1.0)
    │
    ▼  resonance propagation
ENERGY ─── MOOD ─── GENRE ─── ARTIST
```
