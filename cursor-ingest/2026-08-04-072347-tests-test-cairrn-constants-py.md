# tests / test_cairrn_constants.py

#source #python

> path: tests/test_cairrn_constants.py  
> ext: .py  

---

# tests / test_cairrn_constants.py


tests/test_cairrn_constants.py — direct tests for workers/cairrn/_constants.py.

Covers:
  - _COHERENCE_THRESHOLD == W(1) == abs(NEG_EXP_FIXED_POINT)
  - Lambert-W identity: exp(−W(1)) = W(1)
  - Sigma derivation: coh(HOME) == W(1) exactly (HOME at Euler boundary)
  - Ana-Chi near-identity: 𝒜_χ / e ≈ W(1) within documented tolerance
  - Hub coherence partition: agent-context/CODE/HOME coherent; MATH/COMMANDS not


Defines: TestThreshold, TestSigmaDerivation, TestAnaChiNearIdentity, TestHubPartition, TestOtherConstants, test_threshold_is_w1, test_w1_alias, test_threshold_approximate_value, test_lambert_w_identity_holds_in_float, test_sigma_formula, test_sigma_positive, test_sigma_approximate_value, test_home_coherence_equals_w1, test_home_is_coherent, test_ana_chi_over_e_approx_w1, test_near_identity_is_not_exact, test_coherent_hubs_pass, test_incoherent_hubs_reroute, test_coherence_ordering, test_n_shards, test_max_neg_exp_raw, test_hub_primary_shard_coverage, test_hub_primary_shard_in_range

---

## Semantic links

→ [[workers-cairrn-constants]]
→ [[workers-cairrn-z-space]]
→ [[workers-cairrn-layers]]
→ [[engine-gate]]
→ [[MATH]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-constants-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
