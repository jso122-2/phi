# tests / test_cairrn_mycelial.py

#source #python

> path: tests/test_cairrn_mycelial.py  
> ext: .py  

---

# tests / test_cairrn_mycelial.py


tests/test_cairrn_mycelial.py — unit tests for workers/cairrn/mycelial.py.

Covers all 18 pure mycelial formula functions:

Founding spec (Rationale: Mycelial Intelligence in DAWN, 2026-07-13):
  1.  demand()                   — D_i computation
  2.  nutrient_alloc()           — softmax budget distribution
  3.  metabolise()               — metabolic conversion + clamp
  4.  conductance()              — sigmoid edge conductance
  5.  passive_flow()             — diffusion flow
  6.  active_flow()              — bloom/starve transport
  7.  weight_update()            — Hebbian + decay + entrop

Defines: TestDemand, TestNutrientAlloc, TestMetabolise, TestConductance, TestPassiveFlow, TestActiveFlow, TestWeightUpdate, TestShimmerDecay, TestGrowthGate, TestAutophagyTrigger, TestMetaboliteValue, TestAbsorbMetabolite, TestClusterFusionEfficiency, TestClusterFissionOut, TestFHebbianLearning, TestFConnectionDecay, TestFSporeEnergyDecay, TestFAdaptiveCapacity, TestPackageExports, test_all_positive_inputs, test_entropy_reduces_demand, test_zero_inputs, test_negative_drift_align, test_custom_weights, test_sums_to_budget, test_higher_demand_gets_more, test_equal_demands_equal_share, test_empty_returns_empty, test_single_node_gets_full_budget, test_large_demand_spread_stable, test_budget_zero, test_energy_increases_with_nutrients, test_clamp_max, test_clamp_min, test_basal_cost_drains_energy, test_eta_scales_nutrient_gain, test_zero_weight_gives_half, test_large_positive_weight_approaches_one, test_large_negative_weight_approaches_zero, test_output_strictly_between_zero_and_one

---

## Semantic links

→ [[workers-cairrn-mycelial]]
→ [[engine-mycelial-substrate]]
→ [[workers-cairrn-desktop]]
→ [[engine-mycelial]]
→ [[workers-cairrn-formulas]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-desktop-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
