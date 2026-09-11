# COMMANDS — Executable Command Hub

#hub #command

Every command here is **agent-executable** via the `spotify-rip` MCP server.
Source of truth: `mcp_server.commands.SPECS`.

Agents call MCP `run_command(command="/…")` or `list_commands()`. Do not Shell a slash. Legacy one-shot slashes still parse as aliases of `/read` / `/do`. Cursor rule: `.cursor/rules/slash-commands.mdc`.

---

## Connections

→ [[HOME]] ← grand central  
→ [[mcp-server]] — the tools being called  
→ [[attractors]] — sim commands run the attractor engine  
→ [[harmonic-index]] — index commands control the harmonic ring  
→ [[cairrn]] — CAIRRN hub pipeline; `/do cairrn`  
→ [[psspps]] — RAG pipeline powering `/read psspps`  
→ [[environment]] — `/read health` checks the environment  
→ [[graph]] — vault graph worker  
→ [[temporal-index]] — temporal sharding  
→ [[agent-context]] — workflow modes  

---

## How to run

```
list_commands()
run_command(command="/read index")
run_command(command="/do sim 1.5")
run_command(command="/do commit prompt | thinking | outcome")
```

Primary surface:

| Umbrella | Role |
|---|---|
| `/read <sub> …` | Inspect (read-only tools). Bare `/read` loads vault context. |
| `/do <sub> …` | Mutate (sims, inject, commit, enqueue, …). Bare `/do` lists subs. |
| `/read help` `/do help` | List every subcommand. |

---

## `/read` — inspect

MCP: `run_command("/read <sub> …")`. Init-free tools work before the session gate.

| Sub | Alias | Tool | Args | Notes |
|---|---|---|---|---|
| `status` | `/status` | `system_status` | — | Full health — env + index. Init-free. |
| `health` | `/health` | `init_check` | — | Environment / gate check. Init-free. |
| `index` | `/index` | `harmonic_index_state` | — | 8-shard harmonic index. |
| `hub` | `/hub-state` | `hub_state` | — | Harmonic index by station hub. |
| `ana-chi` | `/ana-chi-state` | `ana_chi_state` | `[chi]` | Ana-Chi basin snapshot. |
| `graph` | `/graph-status` | `graph_status` | — | Vault graph health. Init-free. |
| `clean` | `/graph-clean` | `graph_clean` | — | Orphans + dead wikilinks. Init-free. |
| `nest` | `/graph-nest` | `graph_nest` | — | Suggest hub tags. Init-free. |
| `track` | `/graph-track` | `graph_track_state` | — | Usage ledger + git-hot notes. Init-free. |
| `traverse` | `/graph-traverse` | `graph_traverse` | `<seed…>` | `--top-k` `--hops` `--wait`. |
| `vault` | `/vault-hub` | `vault_hub_state` | — | Live vault-hub snapshot. |
| `vault-store` | `/vault-store` | `vault_store_stats` | — | SQL store: nodes, edges, usage. Init-free. |
| `watchdog` | `/watchdog` | `watchdog_state` | — | Stall + contention. |
| `hooks` | `/hooks` | `list_hooks` | — | Pre-hook chain. Init-free. |
| `queue` | `/queue` | `dom_queue_state` | — | DOM house queue. Init-free. |
| `commands` | `/commands` | `list_commands` | — | This catalog. Init-free. |
| `cairrn` | `/cairrn-state` | `cairrn_hub_state` | — | Static CAIRRN hub geometry. |
| `css` | `/cairrn-css` | `cairrn_css_state` | — | CSS bitmask / middle-shard. |
| `m3` | `/cairrn-m3` | `cairrn_m3_gate` | — | M3 quality gate. |
| `temporal` | `/temporal-state` | `temporal_state` | — | Temporal sharding index. |
| `vector` | `/temporal-vector` | `temporal_vector` | — | Hub × window matrix. |
| `temporal-coherence` | `/temporal-coherence` | `temporal_coherence` | — | Ana-Chi coherence of temporal index. |
| `phi` | `/phi-queue` | `phi_queue` | — | Phi dispatcher queue + gate. |
| `shuffle` | `/shuffle-state` | `shuffle_state` | — | Shuffle + gate state. |
| `bus` | `/bus-status` | `bus_status` | — | Mmap ring + worker. Init-free. |
| `poll` | `/bus-poll` | `bus_poll` | `job_id` | Poll a bus job. Init-free. |
| `forecast` | `/forecast` | `forecast_state` | — | Forecast pocket. Init-free. |
| `coherence` | `/coherence-state` | `coherence_state` | `[tail]` | Session trajectory + BMAD. Init-free. |
| `psspps` | `/psspps` | `psspps_query` | `<query…>` | `--alpha` `--top-k` `--wait`. See [[psspps]]. |
| `find` | `/find` | `find_query` | `<query…>` | Pericles exact retrieval. `--wait`. |
| `audit` | `/code-audit` | `code_audit` | `target [mode]` | Read-only code structure audit. |
| `context` | `/context-state` | `system_status` | — | Session-open PSSPPS handshake. Init-free. |

```
/read index
/read psspps what is the Lambert W fixed point --top-k 5
/read find attractors double well
/read traverse HOME --hops 2
/read poll <job_id>
/read audit mcp_server
```

---

## `/do` — mutate

MCP: `run_command("/do <sub> …")`.

| Sub | Alias | Tool | Args | Notes |
|---|---|---|---|---|
| `sim` | `/sim` | `double_well_sim` | `x0` | `--inject`. See [[attractors]]. |
| `neg-exp` | `/neg-exp` | `neg_exp_sim` | `x0` | f(x)=−eˣ → Lambert W. See [[lambert-w]]. |
| `sweep` | `/sweep` | `sweep_attractors` | `[x0_min] [x0_max] [n_points]` | Default [−4, +4], 9 points. |
| `langevin` | `/langevin` | `langevin_sim` | `x0` | Overdamped Langevin. See [[mfpt]]. |
| `mfpt` | `/mfpt` | `mfpt_estimate` | `[noise_scale]` | Mean first passage vs Kramers. |
| `ana-chi` | `/ana-chi` | `ana_chi_sim` | `[chi_0]` | Ana-Chi 5-basin flow. |
| `propagate` | `/propagate` | `harmonic_propagate` | `[steps]` | Advance harmonic ring. |
| `inject` | `/inject` | `harmonic_inject` | `shard_index value` | Direct shard activation. |
| `reset` | `/reset` | `harmonic_reset` | — | Re-seed ring to HOME floor. |
| `hub-inject` | `/hub-inject` | `hub_inject` | `hub_name value` | Inject via station-hub name. |
| `set-goal` | `/set-goal` | `harmonic_set_goal` | `target_shard` | Goal-directed propagation. |
| `clear-goal` | `/clear-goal` | `harmonic_clear_goal` | — | Clear goal vector. |
| `commit` | `/graph-commit` | `graph_commit` | `<prompt> \| <thinking> \| <outcome>` | Session → vault node. |
| `link` | `/graph-link` | `graph_link` | — | Auto-link related nodes. |
| `topo` | `/graph-topo-hubs` | `graph_topo_hubs` | — | Elect hubs. `--write-tags` `--apply-cairrn` `--prefix` `--min-size`. |
| `cairrn-topo` | `/cairrn-topo` | `graph_topo_hubs` | — | Topo election + CAIRRN overlay (`apply_cairrn=True`). |
| `ingest` | `/graph-ingest` | `graph_ingest` | `source_dir` | `--dry-run` `--max-files`. |
| `ingest-source` | `/graph-ingest-source` | `graph_ingest_source` | `<packages…>` | AST-extract Python → `source/` nodes. `--dry-run`. |
| `sync` | `/graph-sync-manifest` | `graph_sync_manifest` | `[manifest_path]` | Pulse hubs from ingest manifest. |
| `track-sync` | `/graph-track-sync` | `graph_track_sync` | — | Heat → `.gitignore` + git index. |
| `annotate` | `/graph-annotate` | `graph_annotate` | `<target_stem> \| <comment>` | Agent commentary node. |
| `vault-project` | `/vault-project` | `vault_project` | `node_id` | Re-materialise session `.md` from SQL. `--force`. |
| `vault-migrate` | `/vault-migrate` | `vault_migrate` | `[batch_size]` | Vault `.md` → SQL upsert. |
| `test` | `/test` | `run_tests` | `[mode]` | `--cov`. |
| `cairrn` | `/cairrn-run` | `cairrn_hub_run` | `hub_name metric` | Full CAIRRN pipeline. See [[cairrn]]. |
| `batch` | `/cairrn-batch` | `cairrn_batch_run` | `[metric]` | CAIRRN across all hubs. |
| `k` | `/cairrn-k` | `cairrn_neuro_k` | `tracer_consensus_value` | Neuro-activation K chain. `--inject`. |
| `record` | `/temporal-record` | `temporal_record` | `hub_name value` | Record hub activation at t=0. |
| `advance` | `/temporal-advance` | `temporal_advance` | `[steps]` | Advance temporal clock. |
| `temporal-reset` | `/temporal-reset` | `temporal_reset` | — | Zero temporal activations. |
| `enqueue` | `/phi-enqueue` | `phi_enqueue` | `kind <query…>` | `--hub` `--shard` `--top-k`. |
| `step` | `/phi-step` | `phi_step` | — | One dispatcher clock tick. |
| `flush` | `/phi-flush` | `phi_flush` | — | Force-dispatch queued phi actions. |
| `clip` | `/clip` | `gemini_clip` | `<query…>` | Clip top-K library tracks. `--top-k`. |
| `seed` | `/shuffle-seed` | `shuffle_seed` | — | Bootstrap CAIRRN prefeed shuffle. |
| `shuffle-step` | `/shuffle-step` | `shuffle_step` | — | One shuffle scheduler tick. |
| `next` | `/shuffle-next` | `shuffle_next` | `[peek_ahead]` | `--peek`. |
| `submit` | `/bus-submit` | `bus_submit` | `task <payload_json…>` | Enqueue mmap/celery job. |
| `wait` | `/bus-wait` | `bus_wait` | `job_id` | `--timeout`. |
| `restart` | `/bus-restart` | `bus_restart` | — | Restart bus worker. |
| `10` | `/10` | `rate_ten` | `[target]` | Rate a project or module out of 10. |
| `notion-tick` | `/notion-tick` | `notion_reservoir_tick` | `[shards] [note]` | `--dry-run`. Fire Notion Reservoir tick: pure edges + Scores update. |
| `notion-state` | `/notion-state` | `notion_reservoir_state` | — | Show shard registry + token status. Init-free. |

```
/do sim 1.5
/do sim -2.0 --inject
/do sweep -10 10 21
/do inject 0 1.0
/do commit did X | thought Y | built Z
/do cairrn HOME 1.0
/do cairrn MATH 0.5
/do test --cov
/do 10 mcp_server
```

### `/cairrn` arity (legacy)

Bare `/cairrn` is **not** `/do cairrn`. It inspects hub geometry (`hub_state`). With two args it runs the pipeline (`cairrn_hub_run`).

```
/cairrn                 → hub_state()          (same family as /read hub)
/cairrn HOME 1.0        → cairrn_hub_run(...)  (same as /do cairrn HOME 1.0)
/read cairrn            → cairrn_hub_state()   (static geometry)
```

---

## Workflow modes

Read the contract file immediately and follow it. MCP `run_command` returns the path; it does not edit files.

| Command | File | One-liner |
|---|---|---|
| `/talk` | `.agent-context/talk.md` | Strategic discussion — align before building. |
| `/explain` | `.agent-context/explain.md` | Plain-language explanation. |
| `/dev` | `.agent-context/dev.md` | Build mode — write, run, iterate. |
| `/modular` | `.agent-context/modular.md` | Package raw output cleanly. |
| `/wire` | `.agent-context/wire.md` | Connect imports, interfaces, pipeline. |
| `/edit` | `.agent-context/edit.md` | Surgical inline fixes. |
| `/clean` | `.agent-context/clean.md` | Fix repo file tree. |
| `/audit` | `.agent-context/audit.md` | Three-layer health audit (waits before fixing). |
| `/read` | `.agent-context/read.md` | Inspect — bare loads vault context; `/read <sub>` dispatches. |

See [[agent-context]].

---

## Find — exact vault retrieval

`/read find <query>` — Pericles-scored exact keyword retrieval. Three-stage funnel.

MCP tool: `find_query(query)`

| Stage | What happens |
|---|---|
| Stage 1 | Top-5 candidates by combined TF-IDF + harmonic score |
| Stage 2 | Pericles re-scoring → top-3 shown to the operator |
| Stage 3 | Single final answer — top-1 by Pericles score |

**The Pericles formula:** `per = |tc_A − Adp_At| · k / x`

| Symbol | Meaning |
|---|---|
| `tc_A` | Total positional term count — earlier keyword hits score higher |
| `Adp_At` | Adaptive harmonic score, temporally decayed by index step count |
| `k` | Combined TF-IDF + harmonic relevance score |
| `N_j` | Normalised Jules entropy score — 0.00 = most focused document |
| `D` | Drift / iwave: `sin(π·β/2)` — positive half-sine, β = k / max\_k |
| `x` | Confidence denominator: `max(|k·N_j|, D)` |

---

## PSSPPS — vault RAG query

`/read psspps <query>` — perspective-oriented RAG against the Obsidian vault.

MCP tool: `psspps_query(query, top_k=3, perspective_alpha=0.5)`

| Parameter | Default | Description |
|---|---|---|
| `query` | — | Natural-language search string |
| `top_k` | 3 | Number of top docs to return (`--top-k`) |
| `perspective_alpha` | 0.5 | 0.0 = pure semantic · 1.0 = pure harmonic (`--alpha`) |

---

## MCP server status

If commands are not responding:
1. Check Cursor Settings → MCP → spotify-rip → Restart
2. Or run `/read health` to verify environment

The server is configured in `.cursor/mcp.json` (remote Streamable HTTP for every clone).  
See [[mcp-server]] for Team Marketplace + Cloud Agents dashboard steps.

---

## Auto-linked

→ [[CODE]]
→ [[live-state]]
→ [[graph]]
→ [[sessions]]
→ [[MATH]]
→ [[agent-context]]
→ [[cairrn]]

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[temporal-index]]

→ [[README]]
→ [[hub-classifier]]
→ [[cursor-skills]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

→ [[config]]
→ [[obsidian-exporter]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-cairrn]]
→ [[mcp-index]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-main]]
