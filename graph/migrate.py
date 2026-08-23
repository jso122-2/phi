"""
graph.migrate — bootstrap and refresh the SQL vault store from disk.

This is the catch-up path: scan every .md in the vault, classify its layer
and hub, and upsert it into the VaultStore.  Designed to be run:

  1. On first boot (empty DB → full vault scan)
  2. On demand after bulk note operations
  3. Never inside a hot request path (it is O(n_notes))

Usage
-----
  # From the mamba env:
  python -m graph.migrate

  # From another module:
  from graph.migrate import run_migrate
  result = run_migrate()

Also migrates .graph-usage.json events into usage_events so the SQL store
reflects the existing heat ledger from the start.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def run_migrate(
    db_path: Path | None = None,
    batch_size: int = 50,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Scan the vault and upsert every note into the SQL store.

    Parameters
    ----------
    db_path    : override the default DB location (for testing)
    batch_size : commit every N nodes (keeps memory stable)
    verbose    : print progress to stdout

    Returns
    -------
    Summary dict with counts by layer and timing.
    """
    from graph.node import VAULT_ROOT, load_vault, SKIP_DIRS
    from graph.layers import layer_of
    from graph.hub_classifier import classify_stem
    from graph.store import VaultStore, DB_PATH

    db = VaultStore(db_path or DB_PATH)

    t0 = time.monotonic()
    nodes = load_vault()  # all three layers

    counts: dict[str, int] = {"stations": 0, "sessions": 0, "ingest": 0, "errors": 0}
    batch: list = []

    def _flush(batch: list) -> None:
        for node, layer, hub in batch:
            try:
                db.upsert_from_vault_node(node, layer, hub)
            except Exception as exc:
                log.warning("migrate: skip %s — %s", node.rel_path, exc)
                counts["errors"] += 1

    for node in nodes:
        rel = node.rel_path.replace("\\", "/")
        layer = layer_of(rel)
        hub: str | None = None
        if layer == "stations":
            hub = classify_stem(node.stem, node.wikilinks[:8])
        elif layer == "sessions":
            hub = None  # sessions carry hub in session_meta; not needed here

        batch.append((node, layer, hub))
        counts[layer] = counts.get(layer, 0) + 1

        if len(batch) >= batch_size:
            _flush(batch)
            batch.clear()

    if batch:
        _flush(batch)

    _migrate_usage_ledger(db, VAULT_ROOT)

    elapsed = time.monotonic() - t0
    result = {
        "elapsed_s": round(elapsed, 2),
        "n_stations": counts.get("stations", 0),
        "n_sessions": counts.get("sessions", 0),
        "n_ingest": counts.get("ingest", 0),
        "n_errors": counts.get("errors", 0),
        "n_total": sum(v for k, v in counts.items() if k != "errors"),
        "db_stats": db.stats(),
    }

    if verbose:
        print(
            f"migrate: {result['n_total']} notes → SQL "
            f"({result['n_stations']} stations, {result['n_sessions']} sessions, "
            f"{result['n_ingest']} ingest) in {result['elapsed_s']}s"
        )

    db.close()
    return result


def _migrate_usage_ledger(db: "VaultStore", vault_root: Path) -> int:
    """
    Read .graph-usage.json and replay individual events into usage_events.

    Each existing entry becomes one synthetic event per signal type so the
    SQL log starts populated.  Only inserts if there are no existing rows
    for that path (avoids double-counting on repeated runs).
    """
    from graph.tracker import LEDGER_PATH

    ledger_path = LEDGER_PATH
    if not ledger_path.exists():
        return 0

    try:
        ledger: dict = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("migrate: could not read usage ledger — %s", exc)
        return 0

    imported = 0
    for rel_path, row in ledger.items():
        # Skip if we already have rows for this path
        existing = db._conn.execute(
            "SELECT COUNT(*) FROM usage_events WHERE rel_path = ?", (rel_path,)
        ).fetchone()[0]
        if existing:
            continue

        for event in ("used", "accessed", "amended"):
            n = int(row.get(event, 0))
            if n > 0:
                ts = row.get(f"last_{event}", "1970-01-01T00:00:00Z")
                db.record_event(rel_path, event, n)
                imported += 1

    return imported


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = run_migrate(verbose=True)
    print(json.dumps(result, indent=2))
