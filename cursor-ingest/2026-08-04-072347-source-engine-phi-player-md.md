# source / engine-phi-player.md

#doc #md

> path: source/engine-phi-player.md  
> ext: .md  

---

# engine/phi_player

#code #module #engine #code

> source_path: engine/phi_player.py  
> package: engine  
> module: engine/phi_player  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/phi_player`  
**Source:** `engine/phi_player.py`

PhiPlayer — CAIRRN-aware playback controller.

Architecture
------------
PhiPlayer closes the feedback loop between what the user *listens to* and
how CAIRRN shapes the *next* shuffle order.

    play_next()           → advance shuffle cursor
                          → peek_and_preload() upcoming tracks into hot cache
                          → step() the dispatcher (CAIRRN CODE tick + hot loader)
                          → return Track to play

    report_play(fraction) → record PlayEvent
                          → inject play fraction into HOME / CODE hubs
                          → force-propagate harmonic shards (2 steps)
                          → CAIRRN gravity vector shifts for next prefeed()

Play-fraction → injection mapping
----------------------------------
The play fraction (0.0 = immediate skip, 1.0 = listened to end) is the
only feedback signal.  Thresholds are chosen to match listener intent:

    fraction ≥ 0.80  →  loved: HOME + CODE injection at full fraction
    fraction  0.40–0.79  →  heard: HOME injection only (moderate resonance)
    fraction < 0.40  →  skipped: no injection (silence is not negative signal)

HOME injection  → reinforces baseline resonance for this shard region
CODE injection  → directly shifts shuffle gravity toward similar tracks

After injection, a 2-step harmonic propagation spreads the activation
through neighbouring shards.  The next shuffle prefeed() reads the updated
shard activations and reorders the gravity vector accordingly.

PlayEvent
---------
Immutable record of one play session.  Stored in a ring buffer on the player.
External callers can read player.history to feed telemetry, analytics, or
learning loops.

Usage
-----
    # Wire at startup

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[mcp-server-tools-phi-clip]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-audio-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
