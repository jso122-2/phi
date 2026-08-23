# tests / test_ana_chi.py

#source #python

> path: tests/test_ana_chi.py  
> ext: .py  

---

# tests / test_ana_chi.py


Tests for sims/ana_chi.py — the Ana-Chi attractor system.

Coverage
--------
  ANA_CHI_CONSTANT              — immutable value = 1.5414
  BASINS                        — 5 basins, correct χ values and ordering
  RATTLE_CHI                    — 3 rattle pockets at 0.99 / 1.96 / 2.67
  nearest_basin()               — correct basin returned for each zone
  cosine_drape()                — nuzzle formula, known values, r=0 ⇒ 0
  rattling_proximity()          — P=1 at rattle centre, symmetry, decay
  temporal_decay_rate()         — range [0.90, 0.98], monotone in gravity
  potential()              

Defines: TestConstant, TestBasins, TestAnaChiBasinMethods, TestNearestBasin, TestCosineDrape, TestRattlingProximity, TestTemporalDecayRate, TestPotential, TestPotentialGrad, TestRunAnaChiFlow, TestSummariseFlow, TestCoherence, TestBiphasicSignal, TestHubBasin, TestHubChiWeights, test_value, test_immutable, test_rattle_chi_count, test_rattle_chi_values, test_count, test_names, test_chi_values, test_true_center_has_highest_gravity, test_true_center_has_highest_memory_decay, test_rattling_pockets, test_true_center_is_not_rattling, test_white_peak_chi_equals_alpha, test_memory_decay_range, setup_method, test_proximity_at_own_chi, test_proximity_decays_away, test_well_value_negative_at_centre, test_well_value_nonpositive_everywhere, test_well_gradient_zero_at_centre, test_well_gradient_sign, test_temporal_decay_step, test_at_true_center, test_at_white_peak, test_at_escape, test_at_boundary

---

## Semantic links

→ [[sims-ana-chi]]
→ [[ana-chi]]
→ [[mcp-server-tools-sims]]
→ [[sims]]
→ [[sims]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-ana-chi-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-ana-chi-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-attractors-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-attractors-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-sims-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
