---
name: read
description: >-
  Inspect umbrella. Dispatches /read <sub> to the matching MCP tool.
  Bare /read returns vault context. No agent spawn — direct tool dispatch.
---
# /read — Inspect Umbrella

This mode does NOT spawn a subagent. It dispatches directly to MCP tools.

## Dispatch rules

| Invocation | Action |
|---|---|
| `/read` (bare) | Call `run_command("/read")` — returns vault hub state + harmonic snapshot |
| `/read <sub>` | Call `run_command("/read <sub>")` immediately |
| `/read help` | Call `list_commands()` and display the /read sub-table |

**Never Shell a /read command. Always use MCP run_command.**

## Sub-command table

### System & health
| Sub | Returns |
|---|---|
| `status` | Full health report — env + index + shard summary |
| `health` | Gate check — quick pass/fail |
| `context` | Alias for status |
| `watchdog` | Race-watchdog stall + contention |
| `hooks` | Pre-hook chain inspection |
| `queue` | DOM house queue snapshot |
| `commands` | Full command catalog |
| `bus` | Mmap ring + worker snapshot |
| `poll <job_id>` | Poll a bus job by id |
| `forecast` | Forecast pocket snapshot |
| `coherence` | Session harmonic trajectory + BMAD pressure |

### Harmonic index
| Sub | Returns |
|---|---|
| `index` | 8-shard harmonic index |
| `hub` | Harmonic index by station hub |
| `ana-chi` | Ana-Chi 5-basin snapshot |

### Vault graph
| Sub | Returns |
|---|---|
| `graph` | Vault graph health — node count, orphans, hub summary |
| `clean` | Orphans + dead wikilinks |
| `nest` | Suggested hub tags for untagged nodes |
| `track` | Usage ledger + git-hot notes |
| `traverse <seed>` | Walk vault from a seed node |
| `vault` | Live vault-hub snapshot |
| `vault-store` | Vault store statistics |

### Search & retrieval
| Sub | Returns |
|---|---|
| `psspps <query>` | PSSPPS vault RAG — perspective-weighted results |
| `find <query>` | Hybrid search: Notion first → vault fallback |
| `audit <target>` | Code structure audit of a file or module |

### CAIRRN
| Sub | Returns |
|---|---|
| `cairrn` | Static CAIRRN hub geometry |
| `css` | CSS bitmask / middle-shard state |
| `m3` | M3 quality gate result |

### Temporal
| Sub | Returns |
|---|---|
| `temporal` | Temporal sharding index state |
| `vector` | Hub × window activation matrix |
| `temporal-coherence` | Ana-Chi coherence of the temporal index |

### Phi & shuffle
| Sub | Returns |
|---|---|
| `phi` | Phi dispatcher queue + gate state |
| `shuffle` | Prefeed shuffle + gate state |

### Notion
| Sub | Returns |
|---|---|
| `notion-state` | Notion Reservoir shard registry + token status |
