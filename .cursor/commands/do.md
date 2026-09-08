---
description: Mutate — sim, inject, commit, enqueue, …
---

The user invoked `/do`. This is a dispatcher, not a shell command.

Call MCP `run_command` immediately with the full slash string.
Do not use Shell. Do not ask the user to run it.

Command: /do $ARGUMENTS

Bare invocation (no sub) lists subcommands via run_command. `help` / `--help` also lists subs.

Subcommands:
- `sim` (`/sim`) → `double_well_sim` — Double-well gradient descent from x0.
- `neg-exp` (`/neg-exp`) → `neg_exp_sim` — Iterate f(x)=−eˣ from x0.
- `sweep` (`/sweep`) → `sweep_attractors` — Sweep double-well initial conditions.
- `langevin` (`/langevin`) → `langevin_sim` — Overdamped Langevin on the double well.
- `mfpt` (`/mfpt`) → `mfpt_estimate` — Mean first passage time vs Kramers.
- `ana-chi` (`/ana-chi`) → `ana_chi_sim` — Ana-Chi 5-basin flow.
- `propagate` (`/propagate`) → `harmonic_propagate` — Advance harmonic propagation.
- `inject` (`/inject`) → `harmonic_inject` — Inject activation into a shard.
- `reset` (`/reset`) → `harmonic_reset` — Re-seed the ring to a warm HOME floor.
- `hub-inject` (`/hub-inject`) → `hub_inject` — Inject via station-hub name.
- `set-goal` (`/set-goal`) → `harmonic_set_goal` — Set goal-directed propagation target.
- `clear-goal` (`/clear-goal`) → `harmonic_clear_goal` — Clear harmonic goal vector.
- `commit` (`/graph-commit`) → `graph_commit` — Write this session as a vault node.
- `link` (`/graph-link`) → `graph_link` — Auto-link semantically related nodes.
- `topo` (`/graph-topo-hubs`) → `graph_topo_hubs` — Elect hubs from wikilink components.
- `cairrn-topo` (`/cairrn-topo`) → `graph_topo_hubs` — Run topology hub election and pipe cairrn_snapshot through CAIRRNBridge overlay.
- `ingest` (`/graph-ingest`) → `graph_ingest` — Ingest a directory into vault nodes.
- `ingest-source` (`/graph-ingest-source`) → `graph_ingest_source` — AST-extract Python modules into source/ nodes.
- `sync` (`/graph-sync-manifest`) → `graph_sync_manifest` — Pulse hubs from an ingest manifest.
- `track-sync` (`/graph-track-sync`) → `graph_track_sync` — Apply heat to .gitignore and the git index.
- `annotate` (`/graph-annotate`) → `graph_annotate` — Write an agent commentary node.
- `test` (`/test`) → `run_tests` — Run the pytest suite.
- `cairrn` (`/cairrn-run`) → `cairrn_hub_run` — Run CAIRRN pipeline for one hub.
- `batch` (`/cairrn-batch`) → `cairrn_batch_run` — Run CAIRRN across all hubs.
- `k` (`/cairrn-k`) → `cairrn_neuro_k` — Neuro-activation K formula chain.
- `record` (`/temporal-record`) → `temporal_record` — Record hub activation at t=0.
- `advance` (`/temporal-advance`) → `temporal_advance` — Advance the temporal clock.
- `temporal-reset` (`/temporal-reset`) → `temporal_reset` — Zero temporal activations.
- `enqueue` (`/phi-enqueue`) → `phi_enqueue` — Enqueue a CAIRRN-gated phi action.
- `step` (`/phi-step`) → `phi_step` — One CAIRRN dispatcher clock tick.
- `flush` (`/phi-flush`) → `phi_flush` — Force-dispatch all queued phi actions.
- `clip` (`/clip`) → `gemini_clip` — Clip top-K library tracks for a query.
- `seed` (`/shuffle-seed`) → `shuffle_seed` — Bootstrap the CAIRRN prefeed shuffle.
- `shuffle-step` (`/shuffle-step`) → `shuffle_step` — One shuffle scheduler tick.
- `next` (`/shuffle-next`) → `shuffle_next` — Advance shuffle cursor.
- `submit` (`/bus-submit`) → `bus_submit` — Enqueue a mmap/celery bus job.
- `wait` (`/bus-wait`) → `bus_wait` — Wait for a bus job.
- `restart` (`/bus-restart`) → `bus_restart` — Restart the bus worker.
- `10` (`/10`) → `rate_ten` — Rate a project or module out of 10.
