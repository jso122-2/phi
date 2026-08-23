# Session: 2026-08-20 09:15 UTC

#session #prompt

**Prompt:**

/dev wire TP-RAR into Phi ranker

---

**Thinking:**

Implemented F_TP_RAR as tp_rar_score. score() stays C_E. compute_scup uses real TP-RAR. candidates() keeps score order then gates below-mean TP-RAR to the back. dt includes abandon fraction so skips bite before the track ages.

---

**Outcome:**

phi/core/_rank_scoring.py: tp_rar_score + signal extractors. ranker.tp_rar/compute_scup/candidates wired. 13 tests in test_phi_tp_rar.py passed. formula_dictionary F_TP_RAR code pointer set.

---

## Graph links discovered

*none detected*

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
