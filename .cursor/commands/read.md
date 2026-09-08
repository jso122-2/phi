---
description: Inspect — bare loads vault context; /read <sub> dispatches.
---

The user invoked `/read`. Bare `/read` is workflow mode (load vault context). `/read <sub>` dispatches a read-only tool.

Call MCP `run_command` immediately with the full slash string.
Do not use Shell. Do not ask the user to run it.

Command: /read $ARGUMENTS

Bare `/read` (no sub): read `.agent-context/read.md` and follow it. `/read help` lists subs.

Subcommands:
- `status` (`/status`) → `system_status` — Full health report — env + index.
- `health` (`/health`) → `init_check` — Environment-only init / gate check.
- `index` (`/index`) → `harmonic_index_state` — Print 8-shard harmonic index.
- `hub` (`/hub-state`) → `hub_state` — Harmonic index by station hub.
- `ana-chi` (`/ana-chi-state`) → `ana_chi_state` — Ana-Chi basin snapshot.
- `graph` (`/graph-status`) → `graph_status` — Vault graph health snapshot.
- `clean` (`/graph-clean`) → `graph_clean` — Scan orphans + dead wikilinks.
- `nest` (`/graph-nest`) → `graph_nest` — Suggest hub tags for untagged nodes.
- `track` (`/graph-track`) → `graph_track_state` — Usage ledger + git-hot notes.
- `traverse` (`/graph-traverse`) → `graph_traverse` — Walk the vault from a seed.
- `vault` (`/vault-hub`) → `vault_hub_state` — Live vault-hub snapshot.
- `watchdog` (`/watchdog`) → `watchdog_state` — Race-watchdog stall + contention.
- `hooks` (`/hooks`) → `list_hooks` — Inspect the append-only pre-hook chain.
- `queue` (`/queue`) → `dom_queue_state` — DOM house queue snapshot.
- `commands` (`/commands`) → `list_commands` — List every slash command and its MCP tool.
- `cairrn` (`/cairrn-state`) → `cairrn_hub_state` — Static CAIRRN hub geometry.
- `css` (`/cairrn-css`) → `cairrn_css_state` — CSS bitmask / middle-shard state.
- `m3` (`/cairrn-m3`) → `cairrn_m3_gate` — M3 quality gate.
- `temporal` (`/temporal-state`) → `temporal_state` — Temporal sharding index state.
- `vector` (`/temporal-vector`) → `temporal_vector` — Hub × window activation matrix.
- `temporal-coherence` (`/temporal-coherence`) → `temporal_coherence` — Ana-Chi coherence of the temporal index.
- `phi` (`/phi-queue`) → `phi_queue` — Inspect phi dispatcher queue + gate.
- `shuffle` (`/shuffle-state`) → `shuffle_state` — Inspect shuffle + gate state.
- `bus` (`/bus-status`) → `bus_status` — Mmap ring + worker snapshot.
- `poll` (`/bus-poll`) → `bus_poll` — Poll a bus job by id.
- `forecast` (`/forecast`) → `forecast_state` — Forecast pocket snapshot.
- `coherence` (`/coherence-state`) → `coherence_state` — Session harmonic trajectory + BMAD pressure signals.
- `psspps` (`/psspps`) → `psspps_query` — PSSPPS vault RAG query.
- `find` (`/find`) → `find_query` — Pericles-scored exact vault retrieval.
- `audit` (`/code-audit`) → `code_audit` — Read-only code structure audit.
- `context` (`/context-state`) → `system_status` — Session-open PSSPPS handshake (via system_status).
