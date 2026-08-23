# FORMULAS — Formula Variable Dictionary

#math #hub

**Source:** `config/formulas/formula_dictionary.yaml`
**Updated:** 2026-07-21

> Primary formula variable reference for the [[HOME]] knowledge graph.
> Canonical lookup table for all variables across formulas in 26 categories.
> Used by [[psspps]] `/find` command as the authoritative variable index.
> Desktop envelope formulas (13 new) canonised 2026-07-21 and wired into [[cairrn]] workers.

**Statistics**
- Total formulas: 95  (77 batch1+2 + 18 vault keep notes + physics scaffold)
- Formula categories: 30
- Sources: 8 envelope images, 13 notebook images, 6 vault keep nodes, MATH.md, dawn-physics-scaffold.md
- Canonical file: `config/formulas/formula_dictionary.yaml`
- Last updated: 2026-07-21

---

## Desktop Formulas (2026-07-21)

New formulas transcribed from physical notes and canonised into the system.
All are implemented as pure functions in `workers/cairrn.py` and run through
`DesktopFormulaInputs` / `run_desktop_formulas()` on every CAIRRN worker tick.

### F_CONSTRAINT_VAR — Constraint Variable
```
x_c = Lh / P − O
```
| Var | Meaning |
|---|---|
| Lh | likelihood |
| P  | possibility |
| O  | opportunity_cost |
Layer: X (pre-pipeline)

### F_FORECAST_SCORE — Forecast Score
```
score = |(D − e) / x_c| · T · Δj
```
| Var | Meaning |
|---|---|
| D   | forecasting_result % |
| e   | math.e (2.71828…) |
| x_c | constraint_variable (F_CONSTRAINT_VAR) |
| T   | temporal_validator |
| Δj  | energy_available |
Layer: X

### F_SCOPE_NAV — Scope Navigation Score
```
z = ||A + J| − β| · x / √D
```
| Var | Meaning |
|---|---|
| A | current_node |
| J | current_objective |
| β | energy_to_move |
| x | boolean_temporal {0,1} |
| D | SHI |
Layer: 2 (neg_exp sharding)

### F_LOCATION_ROUTE — Location Routing Score
```
R_loc = |x / F| · |T · Σ D_w|
```
| Var | Meaning |
|---|---|
| x   | location |
| F   | energy_projected |
| T   | ticks_to_move |
| D_w | distance per waypoint |
Layer: 2

### F_ENERGY_WEIGHTED — Weighted Energy Sum
```
EW = Σ(i=1..n) |x_i − z_i| / A · T_Dw_i · n_w
```
| Var | Meaning |
|---|---|
| x_i   | energy per node |
| z_i   | desirability_cost per node |
| A     | resources |
| T_Dw  | distance_weighted_time |
| n_w   | positive_normalisation |
Layer: 1 (Ana-Chi modulation)

### F_CAIRRN_COMPOSITE — CAIRRN Composite Score
```
Ψ = |z + x| · |1 − c| − |z + x| · |y − c| + Ti
```
| Var | Meaning |
|---|---|
| z  | confidence |
| x  | scope (SCUP coordinate) |
| y  | dawn_data |
| c  | energy_cost |
| Ti | tick_interval |
Layer: X

### F_DELTA_TWO — Second-Order Delta
```
δ₂ = |D_n + T| / |∂p| · O / T
```
| Var | Meaning |
|---|---|
| D_n | semantic_distance |
| T   | time_steps |
| ∂p  | pressure_gradient |
| O   | opportunity_cost |
Layer: 3 (coherence)

### F_ENERGY_CONSUMPTION — Energy Consumption
```
Ec = (|C − A| · T / p) · Tcv
```
| Var | Meaning |
|---|---|
| C   | required_energy |
| A   | current_position |
| T   | temporal_validator |
| p   | performance |
| Tcv | tracer_consensus_value |
Layer: 1

### F_TRACER_CONSENSUS_K — Tracer Consensus Delta
```
K = |Tcv| − D
```
| Var | Meaning |
|---|---|
| Tcv | tracer_consensus_value |
| D   | SHI |
Layer: 3

### F_HEIGHT_NODE — Height Node Component
```
H = |g + A| − Tcv
```
| Var | Meaning |
|---|---|
| g   | global_friction |
| A   | current_mode |
| Tcv | tracer_consensus_value |
Layer: 1

### F_GLOBAL_RZONE — Global R-Zone Component
```
G = |r²| / ∂β · Tcv − β
```
| Var | Meaning |
|---|---|
| r   | rzone_coordinate |
| ∂β  | pressure_gradient |
| Tcv | tracer_consensus_value |
| β   | SHI (δ₁) |
Layer: 1

### F_TICK_WISDOM — Tick Wisdom Score
```
Tws = Tn / K   (where Tn ≥ Tip)
```
| Var | Meaning |
|---|---|
| Tn  | tracer_at_n |
| Tip | tip_value threshold |
| K   | tracer_consensus_delta (F_TRACER_CONSENSUS_K) |
Layer: 3

### F_LOCAL_FRICTION_D — Local Friction Delta
```
fl = |δz − Tks| · (x / z) + β
```
| Var | Meaning |
|---|---|
| δz  | local_friction |
| Tks | tick_weighted_sum |
| x   | confidence |
| z   | SCOP coordinate |
| β   | pressure |
Layer: 1

---

## Implementation

All desktop formulas are pure functions in `workers/cairrn.py`:
- `f_constraint_var`, `f_forecast_score`, `f_cairrn_composite`
- `f_energy_weighted`, `f_energy_consumption`, `f_height_node`
- `f_global_rzone`, `f_local_friction_d`
- `f_scope_nav`, `f_location_route`
- `f_delta_two`, `f_tracer_consensus_k`, `f_tick_wisdom`
- `f_cairrn_z_space` (active -Z scoring — Layer 4)

Pass `DesktopFormulaInputs(...)` to `CAIRRNWorker` or `spawn_hub_worker`.
Results appear in `CAIRRNResult.desktop`, `CAIRRNResult.z_score`, and `to_dict()["desktop"]` / `to_dict()["z_score"]`.

Vault keep-note formulas (semantic field, RAG, physics scaffold, Planck anchors)
are canonical in `config/formulas/formula_dictionary.yaml` but not yet wired
as Python functions — they serve as symbolic reference definitions.

---

---

## Related Nodes

[[MATH]] · [[HOME]] · [[CODE]] · [[COMMANDS]] · [[psspps]]

---

## Variables (Alphabetical)

---

### A — tag_set_A

- **Full name:** tag_set_A
- **Description:** first semantic tag set
- **Type:** input
- **Used in:** F_JACCARD_AFFINITY, F_CONSUMPTION, F_HEIGHT, F_LOCAL_FRICTION, F_ADAPTIVE_CAPACITY, F_FORECAST_INDEX, F_SCUP_FULL

---

### A_count — activation_count

- **Full name:** activation_count
- **Description:** number of activations
- **Type:** input
- **Used in:** F_RADIAL_POSITION

---

### B — tag_set_B

- **Full name:** tag_set_B
- **Description:** second semantic tag set
- **Type:** input
- **Used in:** F_JACCARD_AFFINITY, F_COGNITIVE_PRESSURE

---

### C — required_energy

- **Full name:** required_energy
- **Description:** required cognitive energy
- **Type:** input
- **Used in:** F_LOCAL_FRICTION, F_SUBSTRATE_MODIFICATION

---

### C_i — local_coherence

- **Full name:** local_coherence
- **Description:** coherence score for node i
- **Type:** output
- **Used in:** F_LOCAL_COHERENCE

---

### C_relevance — context_relevance

- **Full name:** context_relevance
- **Description:** contextual relevance score
- **Type:** input
- **Used in:** F_RADIAL_POSITION

---

### Cc — consumption_component

- **Full name:** consumption_component
- **Description:** calculated by F_CONSUMPTION
- **Type:** input
- **Used in:** F_CORE_TRANSFORMATION, F_CONSUMPTION

---

### D — decision_value

- **Full name:** decision_value
- **Description:** computed decision value
- **Type:** output
- **Used in:** F_DECISION

---

### E_new — new_energy

- **Full name:** new_energy
- **Description:** energy after decay
- **Type:** output
- **Used in:** F_SPORE_ENERGY_DECAY

---

### E_old — old_energy

- **Full name:** old_energy
- **Description:** energy before decay
- **Type:** input
- **Used in:** F_SPORE_ENERGY_DECAY

---

### F — forecast_index

- **Full name:** forecast_index
- **Description:** strain/headroom ratio
- **Type:** output
- **Used in:** F_FORECAST_INDEX, F_FORECAST_SMOOTHED

---

### F* — forecast_smoothed

- **Full name:** forecast_smoothed
- **Description:** exponentially smoothed forecast
- **Type:** output
- **Used in:** F_FORECAST_SMOOTHED, F_SCUP_FULL

---

### F*_t-1 — forecast_smoothed_previous

- **Full name:** forecast_smoothed_previous
- **Description:** previous smoothed forecast
- **Type:** input
- **Used in:** F_FORECAST_SMOOTHED

---

### G — global_component

- **Full name:** global_component
- **Description:** calculated by F_GLOBAL
- **Type:** input
- **Used in:** F_CORE_TRANSFORMATION, F_GLOBAL

---

### H — height_component

- **Full name:** height_component
- **Description:** calculated by F_HEIGHT
- **Type:** input
- **Used in:** F_CORE_TRANSFORMATION, F_HEIGHT

---

### K — weight_factor

- **Full name:** weight_factor
- **Description:** importance weight
- **Type:** parameter
- **Used in:** F_TRACER_WISDOM

---

### Keep_Score — keep_score

- **Full name:** keep_score
- **Description:** score for cache retention
- **Type:** output
- **Used in:** F_CACHE_EVICTION

---

### M_SHI — shi_margin

- **Full name:** shi_margin
- **Description:** max(0, SHI − θ_safe)
- **Type:** input
- **Used in:** F_ADAPTIVE_CAPACITY

---

### N — nutrient_headroom

- **Full name:** nutrient_headroom
- **Description:** nutrient/energy headroom
- **Type:** input
- **Used in:** F_ADAPTIVE_CAPACITY

---

### N(i) — neighborhood

- **Full name:** neighborhood
- **Description:** set of neighboring nodes
- **Type:** input
- **Used in:** F_LOCAL_COHERENCE

---

### P — cognitive_pressure

- **Full name:** cognitive_pressure
- **Description:** raw cognitive pressure
- **Type:** output
- **Used in:** F_COGNITIVE_PRESSURE, F_PRESSURE_NORMALIZED, F_FORECAST_INDEX, F_TRACER_ORCHESTRATION

---

### P_safe — safe_threshold

- **Full name:** safe_threshold
- **Description:** safe pressure threshold
- **Type:** parameter
- **Used in:** F_PRESSURE_NORMALIZED

---

### P̂ — pressure_normalized

- **Full name:** pressure_normalized
- **Description:** normalized cognitive pressure
- **Type:** output
- **Used in:** F_PRESSURE_NORMALIZED, F_SCUP_FULL

---

### R — resource

- **Full name:** resource
- **Description:** resource factor
- **Type:** input
- **Used in:** F_SQUARE_ROOT

---

### R_node — radial_position

- **Full name:** radial_position
- **Description:** radial distance in semantic space
- **Type:** output
- **Used in:** F_RADIAL_POSITION

---

### SC — scaling_constant

- **Full name:** scaling_constant
- **Description:** scaling constant
- **Type:** input
- **Used in:** F_SQUARE_ROOT

---

### SCUP — consciousness_coherence

- **Full name:** consciousness_coherence
- **Description:** probability of maintaining coherence
- **Type:** output
- **Used in:** F_SCUP_FULL, F_EMERGENCE_TIMING

---

### SCUP_0 — initial_scup

- **Full name:** initial_scup
- **Description:** SCUP value at t=0
- **Type:** input
- **Used in:** F_SCUP_DECAY

---

### SCUP_t — scup_at_time_t

- **Full name:** scup_at_time_t
- **Description:** SCUP value at time t
- **Type:** output
- **Used in:** F_SCUP_DECAY

---

### SHI — semantic_hash_index

- **Full name:** semantic_hash_index
- **Description:** semantic spatial index
- **Type:** input
- **Used in:** F_SCUP_FULL

---

### S_T — tracer_slack

- **Full name:** tracer_slack
- **Description:** tracer system slack/capacity
- **Type:** input
- **Used in:** F_ADAPTIVE_CAPACITY

---

### S_feedback — success_feedback

- **Full name:** success_feedback
- **Description:** success/outcome feedback
- **Type:** input
- **Used in:** F_RADIAL_POSITION

---

### T — temperature

- **Full name:** temperature
- **Description:** emotional temperature/volatility
- **Type:** input
- **Used in:** F_TILT

---

### Tcurrent — current_time

- **Full name:** current_time
- **Description:** current timestamp
- **Type:** input
- **Used in:** F_TRACER_WISDOM

---

### Tcv — tracer_consensus_value

- **Full name:** tracer_consensus_value
- **Description:** consensus from tracer system
- **Type:** input
- **Used in:** F_CONSUMPTION, F_HEIGHT

---

### Tip — tip_value

- **Full name:** tip_value
- **Description:** information/insight provided
- **Type:** input
- **Used in:** F_TRACER_WISDOM

---

### Tn — tracer_node

- **Full name:** tracer_node
- **Description:** tracer at time n
- **Type:** input
- **Used in:** F_TRACER_WISDOM

---

### Tws — tracer_wisdom_score

- **Full name:** tracer_wisdom_score
- **Description:** calculated by F_TRACER_WISDOM
- **Type:** input
- **Used in:** F_DECISION, F_TRACER_WISDOM

---

### a — activation

- **Full name:** activation
- **Description:** activation level
- **Type:** output
- **Used in:** F_2025_12_14_002, F_TILT, F_SCUP_FULL, F_SUBSTRATE_MODIFICATION, F_SQUARE_ROOT

---

### a_i — activation_i

- **Full name:** activation_i
- **Description:** activation level of neuron i
- **Type:** input
- **Used in:** F_HEBBIAN_LEARNING

---

### a_j — activation_j

- **Full name:** activation_j
- **Description:** activation level of neuron j
- **Type:** input
- **Used in:** F_HEBBIAN_LEARNING

---

### affinity — semantic_affinity

- **Full name:** semantic_affinity
- **Description:** Jaccard similarity score
- **Type:** output
- **Used in:** F_JACCARD_AFFINITY

---

### b — weight_pressure

- **Full name:** weight_pressure
- **Description:** pressure weight
- **Type:** parameter
- **Used in:** F_SCUP_FULL

---

### c — consumption

- **Full name:** consumption
- **Description:** raw metabolic consumption
- **Type:** input
- **Used in:** F_CONSUMPTION, F_SCUP_FULL

---

### d — decay_factor

- **Full name:** decay_factor
- **Description:** frustration decay
- **Type:** input
- **Used in:** F_TILT, F_ROUTING_SPEED, F_SCUP_FULL

---

### decay_rate — decay_rate

- **Full name:** decay_rate
- **Description:** rate of connection decay per tick
- **Type:** parameter
- **Used in:** F_CONNECTION_DECAY, F_SPORE_ENERGY_DECAY

---

### dist_x(i,j) — spatial_distance

- **Full name:** spatial_distance
- **Description:** spatial distance in semantic space
- **Type:** function
- **Used in:** F_LOCAL_COHERENCE

---

### dynamic_priority — dynamic_priority

- **Full name:** dynamic_priority
- **Description:** current priority level
- **Type:** input
- **Used in:** F_CACHE_EVICTION

---

### e — energy

- **Full name:** energy
- **Description:** available energy
- **Type:** input
- **Used in:** F_ROUTING_SPEED, F_SCUP_FULL

---

### emergence_interval — emergence_interval

- **Full name:** emergence_interval
- **Description:** time until tracer emergence
- **Type:** output
- **Used in:** F_EMERGENCE_TIMING

---

### f — friction

- **Full name:** friction
- **Description:** resistance factor
- **Type:** input
- **Used in:** F_2025_12_14_002, F_TILT, F_SCUP_FULL, F_SUBSTRATE_MODIFICATION

---

### f1 — SHI

- **Full name:** SHI (Semantic Hash Index)
- **Description:** Semantic Hash Index
- **Type:** input
- **Used in:** F_2025_12_14_001, F_GLOBAL, F_DECISION

---

### f_speed — routing_speed

- **Full name:** routing_speed
- **Description:** calculated routing priority/speed
- **Type:** output
- **Used in:** F_ROUTING_SPEED

---

### fl — local_friction

- **Full name:** local_friction
- **Description:** calculated by F_LOCAL_FRICTION
- **Type:** input
- **Used in:** F_DECISION, F_LOCAL_FRICTION

---

### g — global_friction

- **Full name:** global_friction
- **Description:** system-wide resistance
- **Type:** input
- **Used in:** F_2025_12_14_001

---

### h — local_friction

- **Full name:** local_friction (raw)
- **Description:** local resistance
- **Type:** input
- **Used in:** F_2025_12_14_001, F_SUBSTRATE_MODIFICATION

---

### j — density

- **Full name:** density
- **Description:** semantic density factor
- **Type:** input
- **Used in:** F_GLOBAL

---

### k — transformation_output

- **Full name:** transformation_output
- **Description:** result of core transformation
- **Type:** output
- **Used in:** F_CORE_TRANSFORMATION

---

### mycelial_position_score — position_score

- **Full name:** position_score
- **Description:** value based on mycelial position
- **Type:** input
- **Used in:** F_CACHE_EVICTION

---

### n — tracer_identity

- **Full name:** tracer_identity
- **Description:** tracer identity/stability factor
- **Type:** input
- **Used in:** F_EMERGENCE_TIMING

---

### p — performance

- **Full name:** performance
- **Description:** performance factor
- **Type:** input
- **Used in:** F_CONSUMPTION

---

### r — rhizomic_coordinate

- **Full name:** rhizomic_coordinate
- **Description:** position in rhizomic space
- **Type:** input
- **Used in:** F_2025_12_14_001, F_GLOBAL

---

### sim(e_i, e_j) — similarity

- **Full name:** similarity
- **Description:** semantic similarity between embeddings
- **Type:** function
- **Used in:** F_LOCAL_COHERENCE

---

### strength — connection_strength

- **Full name:** connection_strength
- **Description:** current connection strength (modified in-place)
- **Type:** input_output
- **Used in:** F_CONNECTION_DECAY

---

### t — target

- **Full name:** target
- **Description:** target distance or value
- **Type:** input
- **Used in:** F_ROUTING_SPEED, F_SCUP_DECAY, F_EMERGENCE_TIMING, F_TRACER_ORCHESTRATION

---

### tick_speed — tick_speed

- **Full name:** tick_speed
- **Description:** system tick rate
- **Type:** input
- **Used in:** F_EMERGENCE_TIMING

---

### time_decay — time_decay

- **Full name:** time_decay
- **Description:** time since last access
- **Type:** input
- **Used in:** F_CACHE_EVICTION

---

### w — weight

- **Full name:** weight
- **Description:** weight of the recursive chamber
- **Type:** output
- **Used in:** F_2025_12_14_001, F_2025_12_14_002

---

### w_N — weight_nutrient

- **Full name:** weight_nutrient
- **Description:** nutrient weight factor
- **Type:** parameter
- **Used in:** F_ADAPTIVE_CAPACITY

---

### w_S — weight_shi

- **Full name:** weight_shi
- **Description:** SHI weight factor
- **Type:** parameter
- **Used in:** F_ADAPTIVE_CAPACITY

---

### w_T — weight_tracer

- **Full name:** weight_tracer
- **Description:** tracer weight factor
- **Type:** parameter
- **Used in:** F_ADAPTIVE_CAPACITY

---

### w_ij — connection_weight

- **Full name:** connection_weight
- **Description:** connection strength i→j
- **Type:** input
- **Used in:** F_LOCAL_COHERENCE

---

### x — confidence

- **Full name:** confidence
- **Description:** confidence level
- **Type:** input
- **Used in:** F_2025_12_14_001, F_2025_12_14_002, F_DECISION, F_TILT, F_ROUTING_SPEED, F_TRACER_ORCHESTRATION

---

### y — scup_coordinate

- **Full name:** scup_coordinate
- **Description:** DAWN SCUP coordinate (vertical)
- **Type:** input
- **Used in:** F_HEIGHT, F_TILT

---

### z — uncertainty

- **Full name:** uncertainty
- **Description:** decision uncertainty
- **Type:** input
- **Used in:** F_DECISION, F_TILT

---

### Δdrift — semantic_drift

- **Full name:** semantic_drift
- **Description:** semantic drift measure
- **Type:** input
- **Used in:** F_SCUP_FULL

---

### Δw_ij — connection_strength_change

- **Full name:** connection_strength_change
- **Description:** change in connection strength between neurons i and j
- **Type:** output
- **Used in:** F_HEBBIAN_LEARNING

---

### α — alpha

- **Full name:** alpha
- **Description:** smoothing factor
- **Type:** parameter
- **Used in:** F_FORECAST_SMOOTHED, F_RADIAL_POSITION

---

### β — beta_weight

- **Full name:** beta_weight
- **Description:** relevance weight
- **Type:** parameter
- **Used in:** F_RADIAL_POSITION

---

### γ — gamma_weight

- **Full name:** gamma_weight
- **Description:** feedback weight
- **Type:** parameter
- **Used in:** F_RADIAL_POSITION

---

### η — learning_rate

- **Full name:** learning_rate
- **Description:** Hebbian learning rate
- **Type:** parameter
- **Used in:** F_HEBBIAN_LEARNING

---

### λ — decay_rate

- **Full name:** decay_rate (temporal)
- **Description:** temporal decay rate
- **Type:** parameter
- **Used in:** F_TRACER_WISDOM, F_SCUP_DECAY

---

### σ — sigmoid

- **Full name:** sigmoid
- **Description:** sigmoid activation function
- **Type:** function
- **Used in:** F_SCUP_FULL

---

### σ² — variance

- **Full name:** variance
- **Description:** variance/volatility measure
- **Type:** input
- **Used in:** F_COGNITIVE_PRESSURE

---

### τ̄ — average_latency

- **Full name:** average_latency
- **Description:** average system latency
- **Type:** input
- **Used in:** F_SCUP_FULL

---

## Formula Index (by category)

Formulas span 30 categories (95 total):

- **Core transformation:** F_CORE_TRANSFORMATION, F_2025_12_14_001, F_2025_12_14_002
- **SCUP / coherence:** F_SCUP_FULL, F_SCUP_CANONICAL, F_SCUP_DECAY, F_PRESSURE_NORMALIZED, F_COGNITIVE_PRESSURE
- **SHI / health:** F_SHI_AGGREGATE, F_SHI_FULL, F_VOICE_EVOLUTION, F_WOLF_REPAIR, F_ENTROPY_LOOP
- **Forecast / smoothing:** F_FORECAST_INDEX, F_FORECAST_SMOOTHED, F_SHANNON_EXTENSION, F_LOAD_COEFFICIENT
- **Routing / speed:** F_ROUTING_SPEED, F_TRACER_ORCHESTRATION, F_ROUTE_R1..R5, F_HANDOFF, F_RESOURCE_ALLOC
- **Tracer system:** F_TRACER_WISDOM, F_TRACER_ORCHESTRATION, F_EMERGENCE_TIMING
- **Adaptive capacity:** F_ADAPTIVE_CAPACITY
- **Semantic / spatial:** F_JACCARD_AFFINITY, F_LOCAL_COHERENCE, F_RADIAL_POSITION, F_GLOBAL, F_HEIGHT, F_COSINE_SIMILARITY, F_EDGE_WEIGHT, F_PATH_COST, F_PATH_REINFORCEMENT, F_PRESSURE_HEATMAP
- **Learning / decay:** F_HEBBIAN_LEARNING, F_CONNECTION_DECAY, F_SPORE_ENERGY_DECAY, F_SHIMMER_DECAY, F_SHIMMER_BASE, F_NUTRIENT_DECAY, F_DECAY_NUTRIENT
- **Decision / friction:** F_DECISION, F_LOCAL_FRICTION, F_TILT, F_ATTRACTION_WEIGHT, F_ATTRACTION_TRIMM
- **Cache / substrate:** F_CACHE_EVICTION, F_SUBSTRATE_MODIFICATION, F_CONSUMPTION, F_SQUARE_ROOT
- **CAIRRN pipeline:** F_CAIRRN_COMPOSITE, F_CAIRRN_COMPOSITE_CONDITION, F_CAIRRN_Z_SPACE, F_DELTA_TWO, F_DELTA_TWO_V2
- **Nutrient / bloom:** F_NUTRIENT_FLOW, F_NUTRIENT_DECAY, F_BLOOM_UPDATE, F_BLOOM_PRESSURE, F_PATH_REINFORCEMENT, F_EDGE_WEIGHT
- **Ash / volcanic:** F_VOLCANIC_ASH, F_ASH_YIELD, F_SHIMMER_BASE, F_CRYSTALLISATION, F_EDGE_VOLATILITY
- **Physics scaffold:** F_PLANCK_TIME, F_PLANCK_LENGTH, F_PLANCK_MASS, F_PLANCK_ENERGY, F_DOUBLE_WELL, F_NEG_EXP
- **Probability / gain:** F_PROBABILITY_GAIN, F_SUCCESS_RATIO, F_CONFIDENCE_SCORE, F_TP_RAR, F_MODEL_ACTIVATION, F_SECONDARY_MODEL_SELECT, F_COGNITIVE_GRAVITY
- **RAG / retrieval:** F_RAG_PRIORITY, F_MANIFOLD, F_SQUASHED_SPACE
- **DAWN pulse:** F_SEMANTIC_DRIFT, F_PULSE_PRESSURE, F_REFLECTION_TENSION, F_SCUP_CANONICAL, F_SHI_FULL

---

## Auto-linked

→ [[phi-routing-diagnosis-2026-08-04]]
→ [[css-m3-prefeed-gate-2026-08-04]]

→ [[2025-05-22-140420-22-5-25-scvhema-bucketed]]

→ [[2025-12-06-123319-rag-formula]]

→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-cli-status-line]]
→ [[pow]]

→ [[mycelial-layer]]
→ [[dawn-physics-scaffold]]
→ [[2025-05-26-141815-semantic-feild-formule]]
→ [[2025-08-09-024311-rationale-mycelial-intelligence-in-dawn]]
→ [[2025-10-01-111154-2025-10-01t21-12-06-646-10-00]]
→ [[2026-01-14-093345-2026-01-14t20-33-46-725-11-00]]

→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-mycelial]]
→ [[2025-05-27-100826-sprint-27-5-25]]
→ [[2025-05-22-062455-sigil-list-22-5-25]]
→ [[2025-08-09-023534-cursor-prompts-mycelium-layer]]
→ [[2025-09-04-060526-2025-09-04t16-05-28-022-10-00]]
