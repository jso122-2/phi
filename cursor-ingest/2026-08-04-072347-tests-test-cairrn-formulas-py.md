# tests / test_cairrn_formulas.py

#source #python

> path: tests/test_cairrn_formulas.py  
> ext: .py  

---

# tests / test_cairrn_formulas.py


tests/test_cairrn_formulas.py — unit tests for workers/cairrn/formulas.py.

Covers all 14 pure formula functions:
  Layer X  : f_constraint_var, f_forecast_score, f_cairrn_composite
  Layer 1  : f_energy_weighted, f_energy_consumption, f_height_node,
             f_global_rzone, f_local_friction_d
  Layer 2  : f_scope_nav, f_location_route
  Layer 3  : f_delta_two, f_tracer_consensus_k, f_tick_wisdom
  Z-Space  : f_cairrn_z_space

Each test covers: basic output, division-by-zero guards, sign behaviour.


Defines: TestConstraintVar, TestForecastScore, TestCairrnComposite, TestEnergyWeighted, TestEnergyConsumption, TestHeightNode, TestGlobalRzone, TestLocalFrictionD, TestScopeNav, TestLocationRoute, TestDeltaTwo, TestTracerConsensusK, TestTickWisdom, TestCairrnZSpace, test_basic, test_zero_possibility_no_crash, test_sign_positive_likelihood_dominant, test_opportunity_cost_subtracts, test_basic_output_finite, test_zero_constraint_var_no_crash, test_euler_baseline, test_scales_with_energy, test_basic_output_finite, test_tick_interval_additive, test_basic, test_zero_resources_no_crash, test_zero_normalisation_no_crash, test_proportional_to_normalisation, test_basic_finite, test_zero_performance_no_crash, test_proportional_to_tracer_consensus, test_basic_finite, test_formula, test_basic_finite, test_zero_pressure_no_crash, test_basic_finite, test_zero_scop_no_crash, test_basic_finite, test_zero_shi_no_crash, test_boolean_temporal_zero_gives_zero

---

## Semantic links

→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-mycelial]]
→ [[FORMULAS]]
→ [[workers-cairrn-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-desktop-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
