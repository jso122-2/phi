# Session: 2026-08-20 08:04 UTC

#session #prompt

**Prompt:**

do we have a formula dictionary going or not? we need a .yaml file that contains all our formulae and the appropriate formulae and their value systems

---

**Thinking:**

The catalog already existed at config/formulas/formula_dictionary.yaml (95 named formulas) but had no first-class value_systems block — constants lived only in Python (ALPHA, KAPPA, HUB_PARAMS, mycelial thetas, e5 gate). Restructured the same canonical YAML into schema 1.1.0 with 13 value systems plus 22 live implementations that were missing from the catalog (CSS/M3/e5/Pericles/Kramers/harmonic propagate/mycelial demand).

---

**Outcome:**

Yes — formula_dictionary.yaml is now the single canon: value_systems (physics α=1.96 κ=0.15, double-well, harmonic ring, station_hubs vs phi_hubs, ana-chi, e5 gate, mycelial, Pericles) plus 117 formulas. Path: config/formulas/formula_dictionary.yaml

---

## Graph links discovered

→ [[2026-08-04-072347-config-formulas-formula-dictionary-yaml]]
→ [[2026-08-04-072347-phi-config-example-yaml]]
→ [[2026-08-04-072347-formulas-md]]
→ [[pipeline-utils-config]]
→ [[MATH]]
→ [[2026-08-04-072347-workers-cairrn-mycelial-py]]

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
