# tests / test_gate.py

#source #python

> path: tests/test_gate.py  
> ext: .py  

---

# tests / test_gate.py


tests/test_gate.py — direct tests for engine/gate.py.

Covers:
  - gate_coherence decay formula
  - COHERENCE_THRESHOLD derivation (W(1) = abs(NEG_EXP_FIXED_POINT))
  - is_coherent threshold boundary
  - gate_pass convenience wrapper
  - tau=0 guard (no ZeroDivisionError)


Defines: TestThresholdDerivation, TestGateCoherence, TestIsCoherent, TestGatePass, test_threshold_equals_w1, test_threshold_value, test_lambert_w_identity, test_zero_steps_is_one, test_decays_with_steps, test_at_tau_equals_exp_neg_one, test_output_in_zero_one, test_tau_zero_no_crash, test_above_threshold, test_at_threshold, test_below_threshold, test_zero_incoherent, test_one_coherent, test_custom_threshold, test_returns_tuple, test_fresh_arm_is_coherent, test_stale_arm_incoherent, test_score_consistent_with_is_coherent

---

## Semantic links

→ [[engine-gate]]
→ [[engine-coherence-gate]]
→ [[engine-cairrn-dispatch]]
→ [[engine-coherence-daemon]]
→ [[engine-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-constants-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-gate-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
