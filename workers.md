# workers

#code #hub

The computation pipeline — Workers wrap callables with logging, timing, error handling, and respawn
guards.  Four modules:

---

## Connections

→ [[CODE]] ← code hub  
→ [[HOME]] ← grand central  
→ [[sims]] — SimWorker wraps sims functions  
→ [[mcp-server]] — BatchWorker used inside MCP tools  
→ [[graph]] — graph worker hub  

---

## Module map

```
workers/
├── base.py           Worker / SimWorker / BatchWorker — core computation units
├── cerberus.py       three-head bind guard (ceb_1, ceb_2, factorial escalation)
├── oesophagus.py     file ingestion pipeline (scan → sentinel → transform → vault write)
└── sentinel.py       sensitive-file gate (extension block, path quarantine, content redaction)
```

---

## `workers/base.py`

### Class hierarchy

```
Worker                ← base; wraps any callable with timing + error capture
├── SimWorker         ← wraps a sims.* function (same interface)
└── BatchWorker       ← runs multiple Workers in sequence, collects results
```

### `Worker`

```python
w = Worker(name="my-worker", fn=some_callable)
result = w.run(*args, **kwargs)   # → WorkerResult
```

| Property | Type | Meaning |
|---|---|---|
| `last` | WorkerResult\|None | Most recent result |
| `history` | list[WorkerResult] | All results ever |

### `WorkerResult`

| Field | Type | Meaning |
|---|---|---|
| `status` | Status | PENDING / RUNNING / DONE / FAILED |
| `value` | Any | Return value of fn |
| `error` | str\|None | Traceback if FAILED |
| `elapsed_s` | float | Wall time in seconds |
| `ok` | bool (property) | True iff status == DONE |

### `BatchWorker`

```python
batch = BatchWorker(workers=[w1, w2, w3])
results = batch.run_all(args_list=[(x0_a,), (x0_b,), (x0_c,)])
batch.all_ok     # True iff all DONE
batch.summary()  # list of {worker, status, elapsed_s, error}
```

---

## `workers/cerberus.py`

Three-headed mathematical respawn guard.

| Bind | Formula | Trigger |
|---|---|---|
| `ceb_1` | `|x - z/A - C - 1|` | soft violation when > τ₁ |
| `ceb_2` | `M! × ceb_1` | hard violation when > τ₂ |

Retry M=0→1→2... escalates factorially.  Hard violation respawns via factory().

```python
guard = CerberusGuard(factory=lambda: my_fn, metric_fn=lambda r: r.score)
result = guard(input_data)
```

---

## `workers/sentinel.py`

Sensitive-file gate run before any content reaches the vault.

Three-pass screen:
1. **Extension block** — `.pem`, `.env`, `.key`, SSH keys etc. blocked entirely
2. **Path quarantine** — files under `.ssh`, `.aws`, `credentials/` etc. blocked
3. **Content redaction** — API keys, tokens, passwords replaced with `[REDACTED]`

```python
report = screen(path)   # → SentinelReport
report.allowed          # False if blocked
report.safe_text        # cleaned text (None if blocked or binary)
```

---

## `workers/oesophagus.py`

Full ingestion pipeline: scan → sentinel gate → transform → Cerberus guard → vault write.

```
source/              scan_directory()
  .txt              → _transform_txt()   — quality metric = non-WS ratio
  .mp3/.flac/...    → _transform_audio() — metadata stub, metric=1.0
  .mp4/.mkv/...     → _transform_video() — metadata stub, metric=1.0
                     ↓
                    evaluate(metric, M) — Cerberus gate
                     ↓
                    write_vault_node()  → sessions/ingest/<ts>-<slug>.md
```

```python
result = ingest(source=Path("~/Downloads"), vault_root=VAULT_ROOT)
result.summary()   # dict with scanned/blocked/redacted/ingested counts
```

---

## Tests

```
tests/test_workers.py        Worker / SimWorker / BatchWorker
tests/test_cerberus.py       ceb_1, ceb_2, evaluate, CerberusGuard
tests/test_oesophagus.py     sentinel screen, classify, scan, ingest, write_vault_node
tests/test_graph_worker.py   run_clean, run_status, run_nest (link resolution regression)
```

All 203 tests pass.

---

## Auto-linked

→ [[attractors]]
→ [[environment]]
→ [[live-state]]
→ [[COMMANDS]]
→ [[psspps]]

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[cursor-skills]]
→ [[index]]
→ [[worker]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[sessions]]

→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[logger]]
→ [[hub-classifier]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]

→ [[git-log]]
→ [[README]]
→ [[2026-07-16-011935-graph-session-start]]

→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[ana-chi]]
→ [[temporal-index]]
→ [[harmonic-index]]
→ [[2026-07-16-011935-knowledge-graph-pre-routing]]
→ [[MATH]]

→ [[graph-logger]]
→ [[graph-init]]
→ [[mcp-server-tools-graph]]
→ [[graph-node]]
→ [[lambert-w]]
→ [[graph-index]]
