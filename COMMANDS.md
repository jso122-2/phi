# COMMANDS — Executable Command Hub

#hub #command

Every command here is **agent-executable** via the `spotify-rip` MCP server.
Agents read `.cursor/rules/slash-commands.mdc` and call the MCP tools directly.

---

## Connections

→ [[HOME]] ← grand central  
→ [[mcp-server]] — the tools being called  
→ [[attractors]] — sim commands run the attractor engine  
→ [[harmonic-index]] — index commands control the harmonic ring  
→ [[cairrn]] — CAIRRN hub pipeline; `/cairrn` commands  
→ [[psspps]] — RAG pipeline powering `/psspps`  
→ [[environment]] — `/health` checks the environment  

---

## Simulation commands

### `/sim <x0>`
Runs the double-well gradient descent from starting position x0.

```
/sim 1.5      → converges to +1.96
/sim -2.0     → converges to -1.96
/sim 0.001    → near saddle point, slow convergence to +1.96
```

MCP tool: `double_well_sim(x0, lr=0.05, alpha=1.96, inject_into_index=True)`

---

### `/neg-exp <x0>`
Iterates f(x) = −eˣ from x0, converges to Lambert W fixed point ≈ −0.5671.

```
/neg-exp 0.0      → 20 steps to x* ≈ -0.5671
/neg-exp -0.5     → already near x*, converges fast
```

MCP tool: `neg_exp_sim(x0)`  
See [[lambert-w]] for the math.

---

### `/sweep`
Sweeps 9 initial conditions across [−4, +4] and runs double-well on each.

```
/sweep                      → default sweep
/sweep -10 10 21            → wider range, 21 points
```

MCP tool: `sweep_attractors(x0_min=-4.0, x0_max=4.0, n_points=9, alpha=1.96)`

---

### `/langevin <x0>`
Overdamped Langevin on V(x)=(x²−α²)². Noise enables thermally-activated escape.

MCP tool: `langevin_sim(x0, noise_scale=2.0, steps=500)`  
See [[mfpt]] for the Kramers rate.

---

### `/mfpt [noise_scale]`
Empirical mean first passage time vs Kramers prediction.

MCP tool: `mfpt_estimate(noise_scale=2.0, n_trials=200)`

---

## Harmonic index commands

### `/index`
Print the current activation state of all 8 harmonic shards.

MCP tool: `harmonic_index_state()`

---

### `/propagate [steps]`
Advance the harmonic wave propagation by N cycles.

```
/propagate        → 1 cycle
/propagate 10     → 10 cycles
```

MCP tool: `harmonic_propagate(steps=1)`

---

### `/inject <shard> <value>`
Directly inject activation into a shard.

```
/inject 0 1.0     → add 1.0 to shard 0 (basin centre 1.96)
/inject 3 2.5     → add 2.5 to shard 3 (basin centre 7.84)
```

MCP tool: `harmonic_inject(shard_index, value=1.0)`

---

### `/reset`
Zero all harmonic index activations and reset the step counter.

MCP tool: `harmonic_reset()`

---

## System commands

### `/status`
Full system health report: environment, packages, harmonic index state.

MCP tool: `system_status()`

---

### `/health`
Environment-only check: Python version, package availability, import smoke-test.

MCP tool: `init_check()`

---

### `/test`
Run the full pytest suite. Returns pass/fail counts and stdout.

```
/test           → standard run
/test --cov     → with coverage on sims/ workers/
```

MCP tool: `run_tests(coverage=False)`

---

## Find — exact vault retrieval

### `/find <query>`
Pericles-scored exact keyword retrieval across the entire Obsidian vault.
Three-stage funnel — no room for error.

```
/find attractors double well
/find Lambert W fixed point
/find harmonic shard propagation
```

MCP tool: `find_query(query)`

**Funnel stages:**

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

See [[psspps]] for the underlying scoring engine.

---

## PSSPPS — vault RAG query

### `/psspps <query>`
Perspective-Oriented Semantic Scored Personalized Parsing Scored query against
the Obsidian vault.  Retrieves relevant nodes, scores them by TF-IDF semantic
similarity blended with the harmonic index perspective, and reports whether RAG
actually helped.

```
/psspps what is the Lambert W fixed point
/psspps how does local propagation work
/psspps explain harmonic sharding
```

MCP tool: `psspps_query(query, top_k=3, perspective_alpha=0.5)`

| Parameter | Default | Description |
|---|---|---|
| `query` | — | Natural-language search string |
| `top_k` | 3 | Number of top docs to return |
| `perspective_alpha` | 0.5 | 0.0 = pure semantic · 1.0 = pure harmonic perspective |

See [[psspps]] for full pipeline documentation.

---

## MCP server status

If commands are not responding:
1. Check Cursor Settings → MCP → spotify-rip → Restart
2. Or run `/health` to verify environment

The server is configured in `.cursor/mcp.json`.  
See [[mcp-server]] for full detail.

---

---

## CAIRRN hub pipeline

### `/cairrn`
Inspect current hub geometry — χ values, gravity, shard assignments, coherence state.

MCP tool: `hub_state()`

---

### `/cairrn <hub> <metric>`
Run a metric through the full three-layer CAIRRN pipeline for the given hub.

```
/cairrn HOME 1.0         → modulated by true_center basin (gravity 3.00)
/cairrn MATH 0.5         → modulated by white_peak basin (gravity 2.00, decay 0.95)
/cairrn CODE 0.85        → modulated by mirror basin (gravity 1.50, decay 0.93)
/cairrn COMMANDS 0.3     → modulated by escape basin (gravity 1.00, decay 0.90)
/cairrn agent-context 2.0  → modulated by boundary basin (gravity 0.50)
```

MCP tool: `cairrn_hub_run(hub_name, metric)`  
See [[cairrn]] for full layer documentation.

---

## Graph worker commands

Session push is `graph_commit`. Code push is git to `.hub.git`. Same vault.

### `/graph-commit`
Write this session as a vault node. MCP: `graph_commit(prompt, thinking, outcome)`

### `/graph-status` `/graph-clean` `/graph-nest`
Read-only vault scan. MCP: `graph_status` / `graph_clean` / `graph_nest`

### `/graph-link` `/graph-traverse` `/graph-topo-hubs`
Link, walk, elect hubs. See [[graph]].

### `/graph-ingest` `/graph-ingest-source`
Ingest a directory or this repo's Python modules into vault nodes.

### `/graph-track` `/graph-track-sync`
Usage-weighted git tracking. Heat = used / accessed / amended.
Only hot vault notes are git-tracked. MCP: `graph_track_state` / `graph_track_sync`

---

## Workflow mode commands (agent skills)

### `/audit`
Full three-layer health audit: vault graph + codebase + environment.  
Outputs a `CRITICAL → HIGH → MEDIUM → LOW → PASS` report.  
Waits for confirmation before fixing anything.

Calls: `graph_status` → `graph_clean` → `init_check` → `system_status` → pytest → mypy

---

### `/talk`
Strategic discussion mode — no file edits, structured reasoning only.  
Output format: `RESTATE → OPTIONS → PICK → OPEN`

---

### `/explain [<topic>]`
Plain-language explanation of whatever was asked. Everyday words, no file edits, no build plan.  
Output format: `IN SHORT → HOW IT WORKS → EXAMPLE`

---

### `/dev`
Build mode — write, run, iterate, ship.

---

### `/modular`
Raw dev output → clean minimal Python package.

---

### `/wire`
Connect all pieces — fix imports, thread config, smoke test every seam.

---

### `/edit`
Surgical inline fix — shape/type/logic bugs, EDA misses.

---

### `/clean`
Fix repo file tree — move, delete, normalise, update `.gitignore`.

---

## Full phi catalog

84 slashes. Source of truth: `mcp_server.commands.SPECS`.
Call MCP `list_commands` or `run_command("/commands")` for the live list.

| Slash | Kind | MCP tool | Args |
|---|---|---|---|
| `/sim` | mcp | `double_well_sim` | x0 |
| `/neg-exp` | mcp | `neg_exp_sim` | x0 |
| `/sweep` | mcp | `sweep_attractors` | [x0_min] [x0_max] [n_points] |
| `/langevin` | mcp | `langevin_sim` | x0 |
| `/mfpt` | mcp | `mfpt_estimate` | [noise_scale] |
| `/ana-chi` | mcp | `ana_chi_sim` | [chi_0] |
| `/ana-chi-state` | mcp | `ana_chi_state` | [chi] |
| `/index` | mcp | `harmonic_index_state` |  |
| `/propagate` | mcp | `harmonic_propagate` | [steps] |
| `/inject` | mcp | `harmonic_inject` | shard_index value |
| `/reset` | mcp | `harmonic_reset` |  |
| `/hub-state` | mcp | `hub_state` |  |
| `/hub-inject` | mcp | `hub_inject` | hub_name value |
| `/set-goal` | mcp | `harmonic_set_goal` | target_shard |
| `/clear-goal` | mcp | `harmonic_clear_goal` |  |
| `/psspps` | mcp | `psspps_query` | <query…> |
| `/find` | mcp | `find_query` | <query…> |
| `/graph-commit` | mcp | `graph_commit` | <prompt> \| <thinking> \| <outcome> |
| `/graph-clean` | mcp | `graph_clean` |  |
| `/graph-nest` | mcp | `graph_nest` |  |
| `/graph-link` | mcp | `graph_link` |  |
| `/graph-status` | mcp | `graph_status` |  |
| `/graph-traverse` | mcp | `graph_traverse` | <seed…> |
| `/graph-topo-hubs` | mcp | `graph_topo_hubs` |  |
| `/cairrn-topo` | mcp | `graph_topo_hubs` |  |
| `/graph-ingest` | mcp | `graph_ingest` | source_dir |
| `/graph-ingest-source` | mcp | `graph_ingest_source` | <packages…> |
| `/graph-sync-manifest` | mcp | `graph_sync_manifest` | [manifest_path] |
| `/graph-track` | mcp | `graph_track_state` |  |
| `/graph-track-sync` | mcp | `graph_track_sync` |  |
| `/graph-annotate` | mcp | `graph_annotate` | <target_stem> \| <comment> |
| `/vault-hub` | mcp | `vault_hub_state` |  |
| `/vault-store` | mcp | `vault_store_stats` |  |
| `/vault-project` | mcp | `vault_project` | node_id |
| `/vault-migrate` | mcp | `vault_migrate` | [batch_size] |
| `/context-state` | mcp | `system_status` |  |
| `/status` | mcp | `system_status` |  |
| `/health` | mcp | `init_check` |  |
| `/test` | mcp | `run_tests` | [mode] |
| `/watchdog` | mcp | `watchdog_state` |  |
| `/hooks` | mcp | `list_hooks` |  |
| `/queue` | mcp | `dom_queue_state` |  |
| `/commands` | mcp | `list_commands` |  |
| `/cairrn-state` | mcp | `cairrn_hub_state` |  |
| `/cairrn` | mcp | `hub_state` |  |
| `/cairrn-run` | mcp | `cairrn_hub_run` | hub_name metric |
| `/cairrn-batch` | mcp | `cairrn_batch_run` | [metric] |
| `/cairrn-css` | mcp | `cairrn_css_state` |  |
| `/cairrn-m3` | mcp | `cairrn_m3_gate` |  |
| `/cairrn-k` | mcp | `cairrn_neuro_k` | tracer_consensus_value |
| `/temporal-state` | mcp | `temporal_state` |  |
| `/temporal-vector` | mcp | `temporal_vector` |  |
| `/temporal-coherence` | mcp | `temporal_coherence` |  |
| `/temporal-record` | mcp | `temporal_record` | hub_name value |
| `/temporal-advance` | mcp | `temporal_advance` | [steps] |
| `/temporal-reset` | mcp | `temporal_reset` |  |
| `/phi-enqueue` | mcp | `phi_enqueue` | kind <query…> |
| `/phi-step` | mcp | `phi_step` |  |
| `/phi-queue` | mcp | `phi_queue` |  |
| `/phi-flush` | mcp | `phi_flush` |  |
| `/clip` | mcp | `gemini_clip` | <query…> |
| `/shuffle-seed` | mcp | `shuffle_seed` |  |
| `/shuffle-step` | mcp | `shuffle_step` |  |
| `/shuffle-next` | mcp | `shuffle_next` | [peek_ahead] |
| `/shuffle-state` | mcp | `shuffle_state` |  |
| `/bus-submit` | mcp | `bus_submit` | task <payload_json…> |
| `/bus-poll` | mcp | `bus_poll` | job_id |
| `/bus-wait` | mcp | `bus_wait` | job_id |
| `/bus-status` | mcp | `bus_status` |  |
| `/bus-restart` | mcp | `bus_restart` |  |
| `/forecast` | mcp | `forecast_state` |  |
| `/code-audit` | mcp | `code_audit` | target [mode] |
| `/10` | mcp | `rate_ten` | [target] |
| `/coherence-state` | mcp | `coherence_state` | [tail] |
| `/do` | dispatcher | — |  |
| `/talk` | workflow | — |  |
| `/explain` | workflow | — |  |
| `/dev` | workflow | — |  |
| `/modular` | workflow | — |  |
| `/wire` | workflow | — |  |
| `/edit` | workflow | — |  |
| `/clean` | workflow | — |  |
| `/audit` | workflow | — |  |
| `/read` | workflow | — |  |

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
