# tests / test_cairrn_desktop.py

#source #python

> path: tests/test_cairrn_desktop.py  
> ext: .py  

---

# tests / test_cairrn_desktop.py


tests/test_cairrn_desktop.py — unit tests for workers/cairrn/desktop.py.

Covers:
  - DesktopFormulaInputs defaults (all None)
  - DesktopFormulaOutputs.to_dict() only returns non-None values
  - run_desktop_formulas: empty inputs → all outputs None
  - run_desktop_formulas: full Z-space inputs → neg_z computed
  - run_desktop_formulas: selective inputs → only matching outputs set
  - Dependency chain: forecast_score requires constraint_var to be computable
  - Dependency chain: tick_wisdom requires tracer_consensus_k to be computable


Defines: TestDesktopFormulaInputsDefaults, TestDesktopFormulaOutputs, TestRunDesktopEmpty, TestRunDesktopZSpace, TestRunDesktopConstraintChain, TestRunDesktopTickWisdomChain, TestRunDesktopComposite, TestRunDesktopEnergyWeighted, test_all_fields_default_none, test_selective_assignment, test_all_fields_default_none, test_to_dict_empty_when_all_none, test_to_dict_only_set_values, test_to_dict_excludes_none, test_empty_inputs_all_none, test_empty_returns_desktopformulaoutputs, _z_inputs, test_neg_z_computed, test_non_z_outputs_none_without_inputs, test_constraint_var_computed, test_forecast_score_needs_constraint_var, test_forecast_score_computed_with_full_chain, test_tracer_consensus_k_computed, test_tick_wisdom_needs_k_and_tracer_n, test_tick_wisdom_computed_with_full_chain, test_composite_computed, test_composite_none_without_all_inputs, test_energy_weighted_computed, test_mismatched_list_lengths_skipped

---

## Semantic links

→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-z-space]]
→ [[CODE]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-desktop-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
