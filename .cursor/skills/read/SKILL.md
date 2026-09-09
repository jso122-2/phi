---
name: read
description: Inspect umbrella for the phi project. Dispatches /read <sub> directly to the matching MCP tool via run_command. No subagent spawn. Use when the user types /read or /read <sub> to inspect system state, vault graph, harmonic index, or search.
---

# /read — Inspect Umbrella

Dispatch **directly via MCP** — do not spawn a subagent.

Call `run_command("/read <sub>")` immediately. Never Shell it.

## Sub-command reference

| `/read <sub>` | Returns |
|---|---|
| `status` | Full health report |
| `health` | Gate check — pass/fail |
| `context` | Alias for status |
| `watchdog` | Stall + contention signals |
| `hooks` | Pre-hook chain |
| `queue` | DOM house queue |
| `commands` | Full command catalog |
| `bus` | Ring + worker snapshot |
| `poll <job_id>` | Poll a bus job |
| `forecast` | Forecast pocket |
| `coherence` | Harmonic trajectory + BMAD |
| `index` | 8-shard harmonic index |
| `hub` | Harmonic index by station hub |
| `ana-chi` | Ana-Chi 5-basin snapshot |
| `graph` | Vault graph health |
| `clean` | Orphans + dead wikilinks |
| `nest` | Suggested hub tags |
| `track` | Usage ledger + git-hot notes |
| `traverse <seed>` | Walk vault from seed |
| `vault` | Live vault-hub snapshot |
| `vault-store` | SQL vault store stats |
| `psspps <query>` | PSSPPS RAG retrieval |
| `find <query>` | Hybrid Notion → vault search |
| `audit <target>` | Code structure audit |
| `cairrn` | CAIRRN hub geometry |
| `css` | CSS bitmask state |
| `m3` | M3 quality gate |
| `temporal` | Temporal sharding state |
| `vector` | Hub × window matrix |
| `temporal-coherence` | Temporal Ana-Chi coherence |
| `phi` | Phi dispatcher queue |
| `shuffle` | Prefeed shuffle state |
