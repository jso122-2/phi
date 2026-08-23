---
hub: ARTIST
shard: 4
basin: 9.80
tags: [hub, music, artist]
---

# ARTIST

#hub

Hub shard 4 — artist and album context in the vault.

Receives injections from:
- `liveness` ([0, 1] — probability of live performance)
- External callers that know whether this artist has a vault note
  (inject 1.0 if a note exists; 0.3 if unknown)

## Spoke context

Artist-specific notes live here as spokes. When this hub activates,
PSSPPS retrieves artist, album, and production credit notes from the vault
to provide biographical and discographic context to the ranker.

Create linked notes here for artists in heavy rotation:

```
music/ARTIST.md
    └── [[Portishead]]
    └── [[Burial]]
    └── [[Talk Talk]]
```

## Links

- [[GENRE]] — artist defines genre
- [[MEMORY]] — artist repeat-listen patterns
- [[VAULT]] — artist notes are the primary retrieval target

## Physics

Basin centre 9.80 = 5·α. Antipodal to PLAYBACK (shard 0) under the
8-shard ring — maximal inhibitory coupling in isometric mode means
ARTIST and PLAYBACK trade activation, preventing them from both being
fully active simultaneously.
