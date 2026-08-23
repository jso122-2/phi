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
    session = make_phi_session()
    session.build()
    shuffle = make_prefeed_shuffle(session)
    shuffle.seed()
    hot_loader = CAIRRNHotLoader()
    dispatcher = make_dispatcher(harmonic_index=session.harmonic_index,
                                 shuffle=shuffle, hot_loader=hot_loader)
    player = PhiPlayer(shuffle=shuffle, dispatcher=dispatcher,
                       hot_loader=hot_loader)

    # Player loop (called from audio thread)
    track = player.play_next()
    # ... audio plays ...
    event = player.report_play(play_fraction=0.95)
    print(event.track.display_name, "→ HOME+CODE injected")

## API

- `class PlayEvent` — Immutable record of one play session.
- `class PhiPlayer` — CAIRRN-aware playback controller.
- `def make_phi_player` — Construct a PhiPlayer bound to the given subsystems.
- `class PhiPipeline` — All phi components, fully wired and ready to use.
- `def make_phi_pipeline` — Wire the complete phi pipeline from a built ``PhiTracerSession``.

## Internal imports

`engine.cairrn_dispatch`, `engine.hot_loader`, `engine.prefeed_shuffle`, `engine.cursor_tracer`

---

## Semantic links

→ [[cairrn]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[mcp-server]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]

## Related notes

→ [[source/engine-prefeed-shuffle]]
→ [[source/mcp-server-tools-phi-dispatch]]
→ [[source/mcp-server-tools-prefeed-shuffle]]
→ [[source/engine-cairrn-dispatch]]
→ [[source/scripts-embed-tracks]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-init]]
→ [[engine-prefeed-shuffle]]
→ [[mcp-server-tools-prefeed-shuffle]]
→ [[engine-cairrn-dispatch]]
→ [[engine-index]]
→ [[mcp-server-tools-phi-dispatch]]
