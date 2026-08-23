# cognitive/forecasting-engine — DAWN Forecast Index

#cognitive #forecasting #dawn #hub

> **Module:** `cognitive/forecasting_engine.py`  
> **Status:** live — driven by `forecast_state` MCP tool  
> **Updated by:** `mcp_server/vault_hub.py` → `live-state.md`

---

## What it does

Computes the **Forecast Index F = P/A** from the live harmonic shard activation state.

| Symbol | Meaning | Source |
|---|---|---|
| P | passion — mean shard activation | `HarmonicIndex.activation_vector()` |
| A | acquaintance — 1 − normalised Shannon entropy | activation distribution focus |
| F | raw Forecast Index = min(1.0, P/A) | cognitive pressure / adaptive capacity |
| F* | EMA-smoothed F (α = 0.30) | rolling average across ticks |

---

## Formula

$$F = \min\!\left(1, \frac{P}{A}\right) = \min\!\left(1,\; \frac{\bar{a}}{1 - H_{\text{norm}}}\right)$$

Where:
- $\bar{a}$ = mean activation across all 8 harmonic shards
- $H_{\text{norm}}$ = $H / \log n$ = normalised Shannon entropy of the activation distribution

Smoothed: $F^* = \alpha F + (1-\alpha) F^*_{t-1}$

---

## Interpretation

| F* range | Status | Meaning |
|---|---|---|
| < 0.25 | 🟢 underloaded | System has surplus capacity — vault focus is wide |
| 0.25–0.55 | 🔵 nominal | Pressure within normal operating range |
| 0.55–0.80 | 🟡 elevated | Cognitive pressure rising — drift accumulating |
| ≥ 0.80 | 🔴 saturated | Predicted stress exceeds adaptive capacity |

> The Forecast Index is structurally analogous to an actuary's **claims-to-surplus ratio**.
> High F means predicted load outstrips available reserves — the system is *underreserved*.

---

## Origin

Reconstructed from `FORMULAS.md` (`F_FORECAST_INDEX`, `F_FORECAST_SMOOTHED`) and
DAWN tick-loop notes. Originally ran as `cognitive.forecasting_engine` on the old
DAWN machines. Re-grounded here against the live harmonic index.

See also: [[FORMULAS]] — variable dictionary entry for `F_FORECAST_INDEX`  
Pitch context: [[keep/2025-10-01-061550-2026-01-07t04-11-40-723-11-00]] — Kuperholz pitch script

---

## Connections

→ [[harmonic-index]] — provides the activation vector P and distribution entropy  
→ [[FORMULAS]] — canonical formula reference `F_FORECAST_INDEX`  
→ [[live-state]] — receives forecast updates after every `forecast_state` call  
→ [[mcp-server]] — `forecast_state` MCP tool invokes this engine  
→ [[mycelial-layer]] — F* maps to node energy and demand allocation  
→ [[HOME]]

---

## Auto-linked

→ [[live-state]]
→ [[dawn-physics-scaffold]]
→ [[COMMANDS]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]

→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-01-16-174325-2026-04-17t00-33-44-969-10-00]]
→ [[2025-10-05-094053-2025-10-05t20-40-55-603-11-00]]
→ [[2025-10-05-034506-monday-formula-sheet-sheet]]
→ [[2025-09-04-063034-2025-09-04t16-30-34-670-10-00]]

→ [[cognitive-forecasting-engine]]
→ [[mcp-server-tools-forecast]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-06-08-062357-fresh-termial-instate-gpt]]
→ [[2026-04-30-164518-2026-05-01t02-45-18-208-10-00]]
→ [[2025-10-03-120206-2025-10-03t22-04-36-490-10-00]]
