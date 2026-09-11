# mcp-server

#code #command

The MCP server — exposes all sims and workers as tools that Cursor (or any MCP host) can call directly.

---

## Connections

→ [[CODE]] ← code hub  
→ [[HOME]] ← grand central  
→ [[COMMANDS]] — the slash commands that invoke these tools  
→ [[sims]] — tools call into sims functions  
→ [[workers]] — tools use Worker/BatchWorker  
→ [[harmonic-index]] — shared `_harmonic_index` lives for server lifetime  
→ [[attractors]] — double-well and neg-exp tools  
→ [[live-state]] — vault hub backwards channel (written after every mutating call)  

---

## Registration

One hosted Streamable HTTP process. Every Cursor client points at the same `url`. A Cursor **Profile** (`cursor.com/@handle`) does not copy MCP to other logins — a **Team** does.

### 1. Host the server (once)

```bash
export SPOTIFY_RIP_MCP_TOKEN='…long random secret…'
python -m mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8000
```

Put that process on a URL every machine can reach (`https://HOST/mcp`). Set the same token on the host. Env: `SPOTIFY_RIP_MCP_TRANSPORT`, `SPOTIFY_RIP_MCP_TOKEN`, `SPOTIFY_RIP_MCP_HOST`, `SPOTIFY_RIP_MCP_PORT` / `PORT`. Local HTTP without auth: `--allow-anon`. `GET /health` is public. SSE is not used (Cloud Agents reject it).

### 2. Your laptop (and every other machine) — automatic on workspace open

Opening this repo in Cursor on **any** machine fires the `workspaceOpen` hook, which runs `.cursor/hooks/install_mcp_global.sh`. The script merges `spotify-rip` into `~/.cursor/mcp.json` so the server is available in **every** Cursor project on that laptop, not just this repo.

Env vars needed on the machine (add to `~/.zshrc` / `~/.bashrc` / system env):

```bash
export SPOTIFY_RIP_MCP_URL=https://HOST/mcp
export SPOTIFY_RIP_MCP_TOKEN=<same token as the host>
```

To run it manually on a machine that has the repo but hasn't opened it yet:

```bash
python scripts/setup_mcp.py
# or with explicit values:
python scripts/setup_mcp.py --url https://HOST/mcp --token <TOKEN>
```

### 3. Every clone / IDE / CLI (git)

Committed `.cursor/mcp.json` (same as `mcp.cloud.example.json`):

```json
{
  "mcpServers": {
    "spotify-rip": {
      "url": "${env:SPOTIFY_RIP_MCP_URL}",
      "headers": {
        "Authorization": "Bearer ${env:SPOTIFY_RIP_MCP_TOKEN}"
      }
    }
  }
}
```

On each machine, export `SPOTIFY_RIP_MCP_URL` (include `/mcp`) and `SPOTIFY_RIP_MCP_TOKEN`. Opening this repo is enough — project MCP wins over `~/.cursor/mcp.json`. Home-dir MCP is **not** synced by login.

One-click install on a machine that is not in the repo:

https://cursor.com/install-mcp?name=spotify-rip&config=eyJ1cmwiOiIke2VudjpTUE9USUZZX1JJUF9NQ1BfVVJMfSIsImhlYWRlcnMiOnsiQXV0aG9yaXphdGlvbiI6IkJlYXJlciAke2VudjpTUE9USUZZX1JJUF9NQ1BfVE9LRU59In19

### 3. Cloud Agents + every linked Cursor account (dashboard)

This repo cannot write the dashboard. Your Cloud Agent environment is **personal**, so each Cursor login has its own MCP dropdown until you put everyone on one Team.

1. Invite every linked login to the same Cursor Team (SSO/invite). Profiles do not federate MCP.
2. [Dashboard → Integrations & MCP](https://cursor.com/dashboard/integrations) → **Team MCP Servers** → add HTTP `https://HOST/mcp` with `Authorization: Bearer …` (Cursor redacts the header after save).
3. **Add to Team Marketplace**. Then [Dashboard → Plugins](https://cursor.com/dashboard?tab=plugins): import this GitHub repo (`.cursor-plugin/marketplace.json` + `cursor-plugin/`). Set the **spotify-rip** plugin to **Required** (or Default On). Configure `MCP_URL` and `MCP_TOKEN` on the plugin.
4. Personal Cloud Agents: [cursor.com/agents](https://cursor.com/agents) → MCP dropdown → enable **spotify-rip** (or the team server). Desktop `mcp.json` is not what Cloud Agent VMs read.
5. Allowlist the same URL under Team Settings → MCP Configuration if the team uses an allowlist (allowlist does not install the server).

| Surface | What attaches the MCP |
|---|---|
| Desktop / CLI, this repo | committed `.cursor/mcp.json` |
| Desktop / CLI, any folder | Team Marketplace plugin **Required**, or the install link |
| Cloud Agents | Team Integrations & MCP + Agents MCP dropdown |
| Other Cursor logins | same Team + Required plugin; not the public Profile |

HTTP binds `0.0.0.0:8000` by default. Stdio remains available as `python -m mcp_server.server` with no `--transport` for a single local machine.

---

## Tool catalog

| Tool | MCP name | House | Slash command |
|---|---|---|---|
| Environment check | `init_check` | clean | `/health` |
| Double-well sim | `double_well_sim` | talk | `/sim <x0>` |
| Neg-exp iteration | `neg_exp_sim` | talk | `/neg-exp <x0>` |
| Sweep initial conditions | `sweep_attractors` | talk | `/sweep` |
| Harmonic index state | `harmonic_index_state` | modular | `/index` |
| Propagate index | `harmonic_propagate` | modular | `/propagate [steps]` |
| Hub state | `hub_state` | modular | — |
| Inject activation | `harmonic_inject` | edit | `/inject <shard> <value>` |
| Hub inject | `hub_inject` | edit | — |
| Reset index | `harmonic_reset` | clean | `/reset` |
| Run tests | `run_tests` | dev | `/test` |
| PSSPPS query | `psspps_query` | wire | — |
| System health | `system_status` | clean | `/status` |
| DOM queue state | `dom_queue_state` | clean | — |
| List hooks | `list_hooks` | clean | — |
| Register hook | `register_hook` | clean | — |
| Vault hub state | `vault_hub_state` | clean | — |

---

## Spawn sequence

On process start, three singletons are created in order:

```python
_harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)   # shared state
_dom_queue      = spawn_houses()                                  # 6 DOM houses opened
_vault_hub      = open_vault_hub(project_root)                    # backwards channel to vault
```

Every tool call passes through `_dom_queue.gate(tool_name)` before executing.  
Every mutating tool call pushes state back to `Spotify-rip/live-state.md` via `_vault_hub`.

---

## DOM Request Queue — 6 houses

| House | Purpose | Tools |
|---|---|---|
| `talk` | Explore the attractor landscape | `double_well_sim`, `neg_exp_sim`, `sweep_attractors` |
| `dev` | Build and validate | `run_tests` |
| `modular` | Shape harmonic structure | `harmonic_index_state`, `harmonic_propagate`, `hub_state` |
| `wire` | Connect knowledge (PSSPPS) | `psspps_query` |
| `edit` | Surgical injection | `harmonic_inject`, `hub_inject` |
| `clean` | Reset and verify | `harmonic_reset`, `init_check`, `system_status`, `dom_queue_state`, `list_hooks`, `register_hook`, `vault_hub_state` |

---

## Vault Hub — backwards channel

`mcp_server/vault_hub.py` enforces a backwards write from MCP → Obsidian vault:

```
Forward:   Spotify-rip/*.md  →  PSSPPS retriever  →  MCP tool results
Backwards: MCP tool results  →  VaultHub.push_*() →  Spotify-rip/live-state.md
```

After every mutating call (`/sim`, `/sweep`, `/propagate`, `/inject`, `/reset`, `/status`),
`live-state.md` is rewritten with the current harmonic state, last sim result,
and DOM queue snapshot.  Obsidian picks it up instantly via its file watcher.

→ See [[live-state]] for the current snapshot.

---

## Shared state

```python
_harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
_dom_queue      = spawn_houses()     # 6 BMAD-trust-gated serialising lanes
_vault_hub      = open_vault_hub(…)  # writes Spotify-rip/live-state.md
```

---

## Starting manually

```bash
mamba activate spotify-rip
spotify-rip-mcp          # via console_scripts entry point (stdio)

# or
python -m mcp_server.server

# Cloud / remote (Streamable HTTP on :8000/mcp)
SPOTIFY_RIP_MCP_TOKEN=… python -m mcp_server.server --transport cloud
```

---

## Auto-linked

→ [[graph]]
→ [[agent-context]]
→ [[sessions]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[psspps]]

→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[cairrn]]

→ [[worker]]
→ [[hub-classifier]]
→ [[temporal-index]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[logger]]

→ [[git-log]]
→ [[README]]

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[MATH]]
→ [[cursor-skills]]

→ [[mcp-server-server]]
→ [[mcp-server-vault-hub]]
→ [[mcp-server-tools-system]]
→ [[mcp-index]]
