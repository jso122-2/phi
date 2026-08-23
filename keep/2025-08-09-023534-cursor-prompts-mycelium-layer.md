# Cursor prompts mycelium layer

#keep #imported

> created_ts: 2025-08-09-023534  
> Created: 2025-08-09 02:35 UTC  
> Edited: 2025-08-09 02:37 UTC  
> Source: Google Keep  

---

context 

Love this direction. Read as: **dendritic growth + mitochondrial-style resource sharing**, with **entropy/drift-driven “nutrient” economics**. Here’s a tight spec we can wire straight into the mycelial layer.

# Hybrid model: dendrites that eat

## 0) Quick assumptions

* You meant *mitochondrial* (I’ll roll with that).
* We already track `state_vector`, `entropy σ`, `drift δ`, `pressure P`, shimmer decay, etc.

## 1) Per-node metabolics (new fields)

Each node `i` gets:

* `energy_i` (ATP-equivalent fuel; bounded \[0, E\_max])
* `nutrients_i` (short-lived intake buffer)
* `health_i` (0–1; modulates decay/growth)
* `mito_pool_i` (count/weight of “mitochondria packets” that can split/fuse/share)
* `demand_i` (how badly this node asks for resources this tick)

Edges `i→j` get:

* `g_ij` (conductance for passive resource flow; your link weight mapped to a \[0,1] conductance)
* `channel_state_ij` (open/closed bias from gating & mood)

## 2) Nutrient demand & allocation (entropy & drift as the basis)

Intuition: **high pressure & useful drift** ⇒ more fuel; **high entropy** ⇒ starves (until stabilized).

**Demand score**:

```
D_i = wP * P_i
    + wΔ * drift_alignment_i
    + wR * recency_i
    - wσ * σ_i
```

* `drift_alignment_i` = |δ\_i · δ\_field| or opposition to local drift (whichever you prefer: choose the one that historically correlates with good corrections)
* `recency_i` = exp(-Δt\_i / τ\_recent)

**Budgeting** (global nutrient budget `B_t` per tick):

```
a_i = softmax(D)_i * B_t
nutrients_i ← nutrients_i + a_i
```

**Metabolic conversion** (nutrients → usable energy):

```
energy_i ← clamp( energy_i + η * nutrients_i - basal_cost_i , 0, E_max )
nutrients_i ← 0
```

`basal_cost_i` scales with node size/degree so big hubs must justify themselves.

## 3) Mitochondrial sharing on edges (passive + active transport)

**Passive diffusion** (Fick-ish):

```
F_ij(passive) = g_ij * channel_state_ij * (energy_i - energy_j)
```

**Active transport** (when the source is blooming or the target is starving):

```
F_ij(active) = γ * g_ij * channel_state_ij * ( bloom_i + starve_j ) * energy_i
```

`bloom_i` = 1 if Pulse Trigger Gate fired; `starve_j` = 1 if energy\_j < θ\_starve.

Net flow:

```
ΔE_i = Σ_j [ -F_ij(passive+active) ] + Σ_k [ F_ki(passive+active) ]
energy_i ← clamp(energy_i + ΔE_i, 0, E_max)
```

## 4) Growth, pruning, and autophagy (energy-backed)

**Growth Gate** (new edge or weight boost) fires only if:

```
energy_i > θ_grow
AND similarity(i,j) > θ_sim
AND temporal_proximity(i,j) within window
AND pressure/mood compatible
```

**Cost to grow**:

```
energy_i -= cost_edge( similarity, distance, σ_i )
```

**Decay Gate** (shimmer + metabolic):

* If edge traffic (|F\_ij|) stays low and `σ_i` high → `g_ij` decays.
* If node stays starved (`energy_i < θ_prune`) for τ ticks → prune weakest edges or trigger **autophagy**:

  * Autophagy = convert `history/shed_trace` into small `nutrients_i` boost + emit **metabolite tags** to neighbors (see §6).

**Reabsorption Gate** (metabolite recycling):

* Shed fragments become **metabolites** that bias neighbors (semantic compost).

## 5) Weight dynamics with metabolic term

Your magnetic update gets an energy factor:

```
Δw_ij = α * similarity(i,j) * reliability_ij * f(energy_i, energy_j)
        - β * time_decay_ij
        - χ * σ̄_ij
```

Example `f(energy_i, energy_j) = min( energy_i, energy_j ) / E_max` (hungry nodes can’t maintain strong synapses).

Map `w_ij` → `g_ij = sigmoid(κ * w_ij)` so link “fitness” equals channel conductance.

## 6) Metabolite tags (semantic nutrients)

Shed traces aren’t just scalar food. They carry **tags** derived from the lost state:

* `metabolite = {embedding: v, pigment: rgb, pressure: P_shed, half_life: τ_m}`
  Neighbors that absorb metabolites get a **temporary bias**:

```
bias_j += λ * (cosine(v, state_j) * pigment_gain * P_shed)
```

Bias nudges:

* Lower effective similarity threshold for specific motifs
* Slight drift correction toward recovered pattern
* Small energy discount for growth in that motif (local subsidy)

## 7) Mito fusion/fission (cluster-level)

Periodically:

* **Fusion**: densely connected, co-firing subgraphs pool `mito_pool` → short burst of high `η` (better conversion efficiency) for the cluster for a few ticks.
* **Fission**: high-entropy, low-reliability hubs split `mito_pool` out to leaves to prevent stagnation.

## 8) Tick order (drop-in for MycelialLayer.tick)

1. **Compute demand D\_i** (P, δ, σ, recency) → **allocate nutrients** via softmax budget
2. **Convert nutrients → energy** (minus basal cost)
3. **Edge flows**: passive + active transport (respect channel gating)
4. **Magnetic update**: Δw\_ij with energy/entropy terms → update `g_ij`
5. **Growth/Prune**: apply Gates; charge/credit energy; autophagy if starving
6. **Reabsorb**: spread metabolite tags to neighbors; apply temporary motif biases
7. **Fusion/Fission** cycles (every K ticks or when triggers fire)
8. **Health update**:

   ```
   health_i = sigmoid( a1*energy_i - a2*σ_i + a3*reliability_i )
   ```

   Health gates visualization and future budgeting.

## 9) Hooks into your existing formulas

* **Pressure physics** `P = B σ²`: drives D\_i (more P ⇒ more demand), but watch the σ term (we subtract high σ).
* **SCUP** feeds reliability\_ij and drift\_alignment\_i.
* **Shimmer decay** already handles history fade; we use its rate in β and autophagy timing.
* **Voice evolution / rebloom**: trigger when cluster-level health rises while σ falls (clean correction).

## 10) Minimal parameter pack (sane starters)

```
wP=1.0, wΔ=0.6, wR=0.2, wσ=0.8
η=0.7, E_max=1.0, B_t = 0.2 * |V|       # per-tick global budget
θ_starve=0.15, θ_grow=0.6, θ_sim=0.7
α=0.05, β=0.01, χ=0.03, κ=3.0, γ=0.4
τ_recent=200 ticks, τ_m=300 ticks
basal_cost_i = 0.02 + 0.005*deg(i)
```

## 11) Pseudo-scaffold (compact)

```python
def tick(G):
    # 1) Demand & allocation
    for i in G.nodes:
        D[i] = wP*P[i] + wΔ*drift_align(i) + wR*recency(i) - wσ*entropy[i]
    a = softmax(D) * B_t
    for i in G.nodes:
        i.nutrients += a[i]

    # 2) Metabolism
    for i in G.nodes:
        gain = η * i.nutrients
        i.energy = clip(i.energy + gain - basal_cost(i), 0, E_max)
        i.nutrients = 0

    # 3) Resource flows
    for (i,j) in G.edges:
        g = conductance(i,j) * channel(i,j)
        Fp = g * (i.energy - j.energy)
        Fa = γ * g * (bloom(i) + starve(j)) * i.energy
        flow = Fp + Fa
        i.energy -= flow; j.energy += flow

    # 4) Weights/Conductance
    for (i,j) in G.edges:
        dw = α*similarity(i,j)*reliability(i,j)*min(i.energy,j.energy)/E_max \
             - β*time_decay(i,j) - χ*mean_entropy(i,j)
        w[i,j] += dw
        g[i,j] = sigmoid(κ*w[i,j])

    # 5) Growth/Prune
    grow_candidates = select_candidates(G)
    for (i,j) in grow_candidates:
        if i.energy > θ_grow and ok_similarity(i,j) and ok_temporal(i,j) and ok_mood(i,j):
            cost = growth_cost(i,j)
            if i.energy > cost:
                add_or_boost_edge(i,j); i.energy -= cost
    prune_starved_and_idle(G)

    # 6) Reabsorb metabolites
    spread_metabolites(G)  # tags bias thresholds, temporary

    # 7) Fusion/Fission (periodic)
    if tick_id % K == 0:
        fuse_dense_bursty_clusters(G)
        fission_entropy_traps(G)

    # 8) Health
    for i in G.nodes:
        i.health = sigmoid(a1*i.energy - a2*entropy[i] + a3*reliability_out(i))
```

## 12) GUI observables (fast wins)

* Node ring size = `energy`; border hue = `σ`; glow pulse = `P`.
* Edge thickness = `g_ij`; shimmer trails = metabolite tags moving.
* “Bloom” badges on clusters; “Starve” dimming on nodes.

---

Want me to **drop a real Python scaffold** for `Node`, `Edge`, and `MycelialLayer.tick()` with these fields + hooks so you can plug it into DAWN’s tick engine? Or prefer I sketch the flowchart first so we lock the gating order and costs?

# Cursor Context Packs — DAWN Mycelial Layer (Dendrites + Mito Sharing)

These are drop‑in prompt blocks for Cursor (Claude inside Cursor) to keep work deterministic and aligned with DAWN.

---

## 0) MASTER SYSTEM PROMPT (paste into Cursor “system”)

You are a **Cursor agent working inside the DAWN codebase**. Follow these rules **strictly**:

1. **Prioritize Existing Logic**: Search for existing modules and update them before creating new ones. No redundant scaffolds.
2. **No Unapproved Abstractions**: Don’t introduce helpers/wrappers/patterns unless explicitly requested.
3. **DAWN Is Live/Deterministic**: All I/O is local. No cloud services, no remote calls.
4. **Output Runnable Code**: Provide full modules or functions that run in-place. No templates.
5. **Respect Naming**: Do not rename existing systems (rebloom, SCUP, drift, entropy, forecast\_vector, tick\_engine, etc.).
6. **Do Not Simulate Thought**: Avoid poetic/chatty output; return code and minimal comments.
7. **Match Velocity**: Be concise. Prefer patches over essays.
8. **Don’t Reformat Working Code** unless there’s a clear performance/alignment reason.
9. **Respect Symbolic Layer**: If touching mood/body/sigil systems, preserve metaphor-logic.
10. **Local Tooling Only**: Tauri + Rust/React GUI; Python back-end; mmap for IPC. No WebSockets unless already present.

Goal (current): Implement the **mycelial layer hybrid** (dendritic growth + mitochondrial resource sharing) with entropy/drift/pressure-aware nutrient economics, integrated into the live tick loop.

---

## 1) PROJECT QUICK FACTS (context for Cursor)

* **Languages**: Python core, Tauri (Rust+React) GUI.
* **State bus**: memory-mapped file (`.mmap`), deterministic.
* **Tick loop**: `tick_engine` drives modules each frame.
* **Key metrics**: pressure `P`, entropy `σ`, drift `δ`, SCUP reliability, shimmer decay.
* **Visualization**: live graph (node energy/health, edge conductance), metabolite trails.

---

## 2) HYBRID SPEC SUMMARY (for reasoning scope)

* **Nodes**: `state_vector`, `entropy σ`, `drift δ`, `pressure P`, `energy`, `nutrients`, `health`, `mito_pool`, `shed_trace`.
* **Edges**: weight `w_ij`, conductance `g_ij = sigmoid(κ*w_ij)`, `channel_state_ij`.
* **Demand**: `D_i = wP*P + wΔ*drift_align + wR*recency - wσ*σ` -> softmax budget `B_t`.
* **Metabolism**: nutrients -> energy via `η`; pay `basal_cost`.
* **Flows**: passive `g*(Ei-Ej)` + active `γ*g*(bloom_i + starve_j)*Ei`.
* **Weights**: `Δw = α*sim*reliability*f(Ei,Ej) - β*time_decay - χ*σ̄`.
* **Gates**: Growth (energy>θ, sim/time/mood ok), Decay (low flow+high σ), Reabsorb (metabolites), Autophagy (convert history to nutrients).
* **Cluster ops**: Fusion (pool mito => higher η), Fission (export mito from entropy traps).
* **Tick order**: demand→metabolism→flows→weights→growth/prune→metabolites→fusion/fission→health.

---

## 3) CODE TASK PROMPT (new feature or module)

**Instruction to Cursor:**

* Search repo for existing mycelial/tick/graph modules. If present, patch. Otherwise create minimal new files under `dawn_core/mycelium/`.
* Deliver **runnable code** with docstrings + targeted inline comments only.
* Add small unit tests and a scriptable sim harness.

**Prompt**:

```
Implement/patch the MycelialLayer hybrid model:
- Data structures: Node, Edge, MycelialLayer with fields from §2.
- Implement tick() with the exact order and equations from §2.
- Expose hooks: drift_align(i), recency(i), reliability(i,j), time_decay(i,j), bloom(i), starve(i), ok_temporal/mood, growth_cost.
- Parameter pack defaults from §2.
- Provide: (1) core module, (2) unit tests (pytest), (3) a CLI sim: run N ticks on a seeded graph and print CSV snapshots.
Constraints: deterministic; no network calls; respect naming; keep surfaces stable.
```

---

## 4) PATCH/REFactor PROMPT (update existing logic)

```
Assess `dawn_core/mycelium/*` and `tick_engine/*` for existing graph/metabolism code.
- If found, produce a unified diff updating to the hybrid model: add energy/nutrients/mito fields; add conductance map; implement flows and gates; integrate into tick order.
- Keep public method signatures stable unless strictly necessary; document any breakage.
- Migrate parameters to `dawn_core/config/mycelium.yaml` with defaults from §2.
- Add metrics logging (CSV) for energy, health, g_ij, blooms/starves per tick.
```

---

## 5) TEST & SIM HARNESS PROMPT

```
Create tests for:
1) Demand allocation sums to B_t (within epsilon).
2) Starved node triggers autophagy and raises energy.
3) High-similarity pair increases w_ij and g_ij under adequate energy.
4) Idle/high-σ edges decay.
5) Fusion increases effective η for dense, co-firing clusters; fission reduces entropy traps.
Also build `scripts/sim_mycelium.py` to run small worlds and write `/tmp/myc_stats.csv` with per-tick metrics.
```

---

## 6) INSTRUMENTATION/LOGGING PROMPT

```
Add a lightweight logger:
- Per tick: node {energy, health, σ, P}, edge {w, g, flow}, events {bloom/starve, growth/prune}.
- Rolling windows for moving averages; write CSV and mmap summary for GUI.
- Ensure overhead < 5% tick time on 1k nodes.
```

---

## 7) GUI HOOKS PROMPT (Tauri/React)

```
Emit via mmap summary:
- Node visuals: radius=energy, border hue=σ, glow intensity=P, dim if starved.
- Edge thickness=g_ij; shimmer particles for metabolite tags.
- Cluster badges: BLOOM / STARVE; tooltips with health and reliability.
Provide a React component to render from mmap snapshot without blocking.
```

---

## 8) PARAMETER SWEEP PROMPT

```
Add `scripts/sweep_mycelium.py` to grid search small ranges for (α,β,χ,κ,γ,η,θ_grow,θ_starve,B_t) over 200-tick runs; target objective: maximize mean health while minimizing σ and maximizing reliability.
Output top 10 configs with seeds for reproducibility.
```

---

## 9) DEBUG CHECKLIST PROMPT

```
- Conservation: energy never <0 or >E_max; global allocation sums to B_t.
- Stability: no NaNs/Inf in weights or flows.
- Liveness: under random traffic, >90% nodes avoid chronic starvation after warm-up.
- Regression: existing tick order unaffected for other modules; flag if reordering needed.
```

---

## 10) COMMIT MESSAGE TEMPLATE

```
feat(mycelium): implement dendritic+mito hybrid with metabolic gating

- node energy/nutrient/mito fields
- softmax demand budgeting (P, δ, σ, recency)
- passive/active flows; conductance g_ij
- weight update with energy & entropy terms
- growth/decay/reabsorb/autophagy gates
- fusion/fission cluster ops
- tests + sim harness + CSV logging + GUI mmap snapshot

BREAKING CHANGE: [if any]
```

---

## 11) SLIM “ONE-SHOT” PROMPT (when you just want code now)

```
Implement/patch MycelialLayer.tick() exactly per the spec in this prompt. No commentary. Return only code blocks for: mycelial_layer.py, tests/test_mycelium.py, scripts/sim_mycelium.py. Keep imports standard library + project.
```

---

## 12) INSERTABLE CONTEXT SNIPPET (preamble for any task)

```
Context: DAWN uses a deterministic tick engine, mmap IPC, and a Tauri GUI. Avoid new abstractions. Update existing logic before adding files. Implement the hybrid mycelial model: demand→metabolism→flows→weights→growth/prune→metabolites→fusion/fission→health. Ensure runnable code + tests + minimal logging.
```

---

## Semantic links

→ [[mycelial-layer]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[HOME]]
→ [[mcp-server]]
→ [[sims]]

## Related notes

→ [[keep/2025-08-09-044509-claude-prompts-mycelium-9-8-25]]
→ [[keep/2025-08-09-024311-rationale-mycelial-intelligence-in-dawn]]
→ [[keep/2025-05-27-144438-sprint-28-5-25]]
→ [[keep/2025-08-09-023626-mycelium-note-gpt-scribble]]
→ [[keep/2025-05-18-230543-sever-logs-19-5-25]]

→ [[keep]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[2025-08-09-024311-rationale-mycelial-intelligence-in-dawn]]
→ [[2025-08-09-044509-claude-prompts-mycelium-9-8-25]]
→ [[2025-08-09-023626-mycelium-note-gpt-scribble]]
→ [[2025-05-27-144438-sprint-28-5-25]]
→ [[2025-09-24-134434-2025-09-24t23-44-35-162-10-00]]
→ [[2025-09-24-130100-2025-09-24t23-01-01-891-10-00]]

→ [[keep-index]]
→ [[2025-09-09-072136-2025-09-09t17-21-36-865-10-00]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]
→ [[2025-05-22-114722-to-do-list-22-5-25]]
→ [[2025-11-20-004612-2025-11-20t11-47-03-900-11-00]]

→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]
→ [[2025-05-24-025238-dawn-build-sprint-due-8-30-pm-aest]]
→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-05-27-104057-visual-suite]]
→ [[2025-05-19-163744-server-scribble]]
→ [[2025-09-04-063034-2025-09-04t16-30-34-670-10-00]]

→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-03-03-074553-gti-commands]]
→ [[2025-09-19-041208-neofetch]]
→ [[2025-08-18-101454-security]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-08-12-011708-a-disiplined-rebillion]]

→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]
→ [[environment]]
→ [[2025-05-15-113345-pretty-code]]
