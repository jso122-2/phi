# Session: 2026-08-20 08:49 UTC

#session #prompt

**Prompt:**

look for time adjusted risk penalised return pls

---

**Thinking:**

TARRP was not in the vault as an acronym. Exact match is F_TP_RAR Time-Penalised Risk Adjusted Return in formula_dictionary.yaml. Same quantity, word order swapped. Used as TP-RAR inside phi ranker SCUP.

---

**Outcome:**

Found F_TP_RAR: TP_RAR_E = (C_E - (1-cl_E)*lam - dt*p) / TP_RAR_conf_ma. Downstream: F_SECONDARY_MODEL_SELECT, F_SCUP_CANONICAL, phi/core/ranker.py compute_scup.

---

## Graph links discovered

→ [[2025-05-22-140420-22-5-25-scvhema-bucketed]]
→ [[2025-05-15-095857-server-schema-architecture-15-5-25]]
→ [[2026-08-20-080413-do-we-have-a-formula-dictionary-going-or-not]]
→ [[2026-08-20-084740-find-the-tarrp-formula]]
→ [[FORMULAS]]
→ [[mcp-server-tools-phi-dispatch]]

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
