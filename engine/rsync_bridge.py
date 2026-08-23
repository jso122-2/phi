"""
RsyncBridge — real-time filesystem → Obsidian graph synchronisation daemon.

Watches one or more source directories (project root, phi/, etc.) with
kqueue/inotify events (via watchdog) and triggers an incremental graph
refresh within milliseconds of a file save — replacing the 5-minute crawl
poll cycle.

Pipeline per change event
─────────────────────────
    file saved in watched dir
        ↓  (debounce 400 ms — batches rapid multi-file saves)
    RsyncBridge._flush()
        ↓
    SambaOrchestrator.refresh()   ← in-process, no HTTP
        ↓
    (optional) VaultWriter stub   ← writes a minimal .md into vault so the
                                     changed file immediately has a graph node
        ↓
    log summary

CLI:
    python -m engine.rsync_bridge [options]

    --config PATH           config.yaml path (default: config/config.yaml)
    --checkpoint PATH       model checkpoint (auto-detected if omitted)
    --watch PATH [PATH …]   additional dirs to watch (project root + vault
                            are always included)
    --debounce-ms N         batch window in ms (default: 400)
    --no-stub               don't write vault stubs for changed source files
    --dry-run               log actions but don't write vault or call refresh
    --log-level LEVEL       DEBUG / INFO / WARNING (default: INFO)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Set

# ── Load .env before anything project-local ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print(
        "ERROR: watchdog not installed.  Run: pip install watchdog>=4.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

import yaml

logger = logging.getLogger("rsync_bridge")

# ── File types that actually matter for the graph ────────────────────────────
_WATCHED_SUFFIXES: Set[str] = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
    ".js", ".ts", ".tsx", ".jsx",
}

_SKIP_DIRS: Set[str] = {
    "__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "env", "build", "dist",
    "checkpoints", "logs", ".cursor",
}


# ──────────────────────────────────────────────────────────────────────────────
# Debounce collector
# ──────────────────────────────────────────────────────────────────────────────

class ChangeBuffer:
    """
    Accumulates filesystem events during a debounce window, then fires once.

    Thread-safe: events arrive on watchdog's internal thread; flush() is
    called from a dedicated timer thread.
    """

    def __init__(self, debounce_ms: int, callback) -> None:
        self._debounce = debounce_ms / 1000.0
        self._callback = callback
        self._lock = threading.Lock()
        self._pending: Set[str] = set()
        self._timer: Optional[threading.Timer] = None

    def push(self, path: str) -> None:
        with self._lock:
            self._pending.add(path)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            paths = set(self._pending)
            self._pending.clear()
            self._timer = None
        if paths:
            self._callback(paths)


# ──────────────────────────────────────────────────────────────────────────────
# Watchdog handler
# ──────────────────────────────────────────────────────────────────────────────

class GraphSyncHandler(FileSystemEventHandler):
    """Forward meaningful file changes into ChangeBuffer."""

    def __init__(self, buffer: ChangeBuffer) -> None:
        super().__init__()
        self._buf = buffer

    def _relevant(self, path: str) -> bool:
        p = Path(path)
        # Skip hidden and blacklisted dirs
        for part in p.parts:
            if part.startswith(".") and part not in {".", ".."}:
                return False
            if part in _SKIP_DIRS:
                return False
        return p.suffix.lower() in _WATCHED_SUFFIXES

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._relevant(event.src_path):
            self._buf.push(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._relevant(event.src_path):
            self._buf.push(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._relevant(event.dest_path):
            self._buf.push(event.dest_path)


# ──────────────────────────────────────────────────────────────────────────────
# Vault stub writer
# ──────────────────────────────────────────────────────────────────────────────

_STUB_SUBDIR = "agent-stubs/code-mirror"


def _write_vault_stub(vault_path: Path, src_path: str, dry_run: bool) -> None:
    """
    Create or update a minimal Obsidian note that mirrors the changed source
    file.  This gives the file a stable graph node immediately, before the
    full re-encode pass propagates its embeddings.

    The stub lives in agent-stubs/code-mirror/ and is never confused with
    curated vault notes.
    """
    p = Path(src_path)
    # Derive a stable title from the relative path inside the project
    try:
        project_root = Path(__file__).parent.parent
        rel = p.relative_to(project_root)
        title = str(rel).replace("/", " · ").replace("\\", " · ")
    except ValueError:
        title = p.name

    stub_dir = vault_path / _STUB_SUBDIR
    stub_path = stub_dir / f"{title}.md"

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"---\n"
        f"source: {src_path}\n"
        f"updated: {now}\n"
        f"type: code-mirror\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"Auto-mirrored by RsyncBridge from `{src_path}`.\n\n"
        f"Last change detected: {now}\n"
    )

    if dry_run:
        logger.info(f"[dry-run] would write stub → {stub_path}")
        return

    stub_dir.mkdir(parents=True, exist_ok=True)
    tmp = stub_path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(stub_path)
    logger.debug(f"Stub written: {stub_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Main bridge
# ──────────────────────────────────────────────────────────────────────────────

class RsyncBridge:
    """
    Persistent bridge: watches filesystem, refreshes graph on changes.

    Args:
        config_path:    path to config/config.yaml
        checkpoint:     model checkpoint path (auto-detected if None)
        extra_watches:  additional dirs to watch beyond project root + vault
        debounce_ms:    ms to wait before flushing a batch of changes
        write_stubs:    whether to write vault stubs for changed source files
        dry_run:        log but don't write or refresh
    """

    def __init__(
        self,
        config_path: str,
        checkpoint: Optional[str] = None,
        extra_watches: Optional[list] = None,
        debounce_ms: int = 400,
        write_stubs: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._config_path = config_path
        self._checkpoint = checkpoint
        self._dry_run = dry_run
        self._write_stubs = write_stubs
        self._orch = None
        self._vault_path: Optional[Path] = None

        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        # Resolve vault path (env overrides config)
        vault_raw = (
            os.environ.get("SAMBA_VAULT_PATH")
            or os.environ.get("OBSIDIAN_VAULT_PATH")
            or cfg.get("graph", {}).get("vault_path", "~/Documents/obsidian-vault")
        )
        self._vault_path = Path(os.path.expandvars(vault_raw)).expanduser()

        # Resolve watch roots
        project_root = str(Path(__file__).parent.parent.resolve())
        self._watch_roots: list[str] = [project_root, str(self._vault_path)]
        for w in (extra_watches or []):
            p = Path(w).expanduser().resolve()
            if p.exists():
                self._watch_roots.append(str(p))

        # Debounce buffer wires into _flush
        self._buf = ChangeBuffer(debounce_ms=debounce_ms, callback=self._flush)
        self._observer = Observer()
        self._last_refresh_ts: float = 0.0
        self._total_refreshes: int = 0
        self._refresh_lock = threading.Lock()   # prevent concurrent crawl storms

    # ── Lazy orchestrator load ────────────────────────────────────────────────

    def _get_orch(self):
        if self._orch is not None:
            return self._orch
        try:
            from inference import SambaOrchestrator
            ckpt = self._checkpoint or self._find_checkpoint()
            if ckpt is None:
                logger.warning("No checkpoint found — graph refresh skipped until training completes.")
                return None
            self._orch = SambaOrchestrator(
                checkpoint_path=ckpt,
                config_path=self._config_path,
            )
            logger.info(f"Orchestrator loaded from {ckpt}")
        except Exception as exc:
            logger.error(f"Failed to load orchestrator: {exc}")
        return self._orch

    def _find_checkpoint(self) -> Optional[str]:
        import glob as _glob
        base = Path(__file__).parent.parent / "checkpoints"
        best = base / "best.pt"
        if best.exists():
            return str(best)
        candidates = sorted(_glob.glob(str(base / "perpetual_step_*.pt")))
        if candidates:
            return candidates[-1]
        candidates = sorted(_glob.glob(str(base / "epoch_*.pt")))
        return candidates[-1] if candidates else None

    # ── Flush callback (called from timer thread) ─────────────────────────────

    def _flush(self, paths: Set[str]) -> None:
        n = len(paths)
        logger.info(f"[rsync-bridge] {n} file(s) changed — triggering graph refresh")
        for p in sorted(paths):
            logger.debug(f"  changed: {p}")

        # Optional vault stubs
        if self._write_stubs and self._vault_path:
            source_paths = [
                p for p in paths
                if not str(p).startswith(str(self._vault_path))
            ]
            for p in source_paths:
                try:
                    _write_vault_stub(self._vault_path, p, self._dry_run)
                except Exception as exc:
                    logger.warning(f"Stub write failed for {p}: {exc}")

        # Graph refresh — non-blocking acquire so rapid events skip rather than queue
        if self._dry_run:
            logger.info("[dry-run] skipping orch.refresh()")
            return

        if not self._refresh_lock.acquire(blocking=False):
            logger.debug("Refresh already in progress — skipping duplicate trigger")
            return

        try:
            orch = self._get_orch()
            if orch is None:
                logger.debug("Orchestrator not ready — skipping refresh")
                return

            t0 = time.monotonic()
            orch.refresh()
            elapsed = time.monotonic() - t0
            self._total_refreshes += 1
            self._last_refresh_ts = time.time()
            G = orch.graph.nx_graph
            n_nodes = G.number_of_nodes()
            n_edges = G.number_of_edges()
            logger.info(
                f"[rsync-bridge] refresh #{self._total_refreshes} done "
                f"in {elapsed:.2f}s — {n_nodes} nodes, {n_edges} edges"
            )

            # ── CAIRRN IPC: encode graph topology as hub signals ──────────────
            # ForestFloor.heartbeat() drains /tmp/samba_cairrn_cmds.json on
            # each poll tick, so phi's harmonic ring reacts to vault changes
            # without any direct import of phi from here.
            self._write_cairrn_commands(n_nodes, n_edges)

        except Exception as exc:
            logger.error(f"orch.refresh() failed: {exc}", exc_info=True)
        finally:
            self._refresh_lock.release()

    # ── CAIRRN IPC helpers ────────────────────────────────────────────────────

    _CAIRRN_IPC_CMD_FILE: str = "/tmp/samba_cairrn_cmds.json"

    def _write_cairrn_commands(self, n_nodes: int, n_edges: int) -> None:
        """
        Convert vault topology metrics into CAIRRN hub commands and append them
        to the IPC command file so phi's ForestFloor picks them up on the next
        heartbeat tick.

        Hub routing mirrors ForestFloor / CairnBridge.ingest_vault_snapshot():
            HOME          ← chi (graph shape)      normalised from euler χ estimate
            MATH          ← edge density (β₁/V)     structural complexity
            CODE          ← node density (V/5000)   symbol volume
            agent-context ← change burst (n_changed/V) recent write activity
        """
        import json as _json
        try:
            V = max(n_nodes, 1)
            E = max(n_edges, 0)

            cmds = [
                # HOME — graph shape signal (nodes as proxy for χ magnitude)
                {"hub": "HOME",          "value": min(1.0, V / 2000.0)},
                # MATH — structural complexity (edge density)
                {"hub": "MATH",          "value": min(1.0, E / V)},
                # CODE — symbol volume
                {"hub": "CODE",          "value": min(1.0, V / 5000.0)},
                # agent-context — recent change burst proportional to changed files
                {"hub": "agent-context", "value": min(1.0, self._total_refreshes / 50.0)},
            ]

            tmp = self._CAIRRN_IPC_CMD_FILE + ".tmp"
            with open(tmp, "w") as fh:
                _json.dump(cmds, fh)
            os.replace(tmp, self._CAIRRN_IPC_CMD_FILE)
            logger.debug(
                "[rsync-bridge] CAIRRN IPC: wrote %d hub commands (V=%d E=%d)",
                len(cmds), n_nodes, n_edges,
            )
        except Exception as exc:
            logger.warning(f"[rsync-bridge] CAIRRN IPC write failed (non-fatal): {exc}")

    # ── Start / run ───────────────────────────────────────────────────────────

    def start(self) -> None:
        handler = GraphSyncHandler(self._buf)
        for root in self._watch_roots:
            if os.path.isdir(root):
                self._observer.schedule(handler, root, recursive=True)
                logger.info(f"[rsync-bridge] watching: {root}")
            else:
                logger.warning(f"[rsync-bridge] watch root not found (skipped): {root}")

        self._observer.start()
        logger.info(
            f"[rsync-bridge] live — debounce={self._buf._debounce*1000:.0f}ms "
            f"stubs={'on' if self._write_stubs else 'off'} "
            f"dry_run={self._dry_run}"
        )

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
        logger.info("[rsync-bridge] stopped")

    def run_forever(self) -> None:
        self.start()
        try:
            while self._observer.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RsyncBridge — real-time Cursor → Obsidian graph sync",
    )
    p.add_argument("--config", default=None, help="Path to config.yaml")
    p.add_argument("--checkpoint", default=None, help="Model checkpoint path")
    p.add_argument("--watch", nargs="*", default=[], metavar="PATH",
                   help="Additional directories to watch")
    p.add_argument("--debounce-ms", type=int, default=400,
                   help="Debounce window in ms (default: 400)")
    p.add_argument("--no-stub", action="store_true",
                   help="Don't write vault stubs for changed source files")
    p.add_argument("--dry-run", action="store_true",
                   help="Log actions but don't write or call refresh")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Resolve config path
    project_root = Path(__file__).parent.parent
    config_path = args.config or str(project_root / "config" / "config.yaml")

    bridge = RsyncBridge(
        config_path=config_path,
        checkpoint=args.checkpoint,
        extra_watches=args.watch,
        debounce_ms=args.debounce_ms,
        write_stubs=not args.no_stub,
        dry_run=args.dry_run,
    )
    bridge.run_forever()


if __name__ == "__main__":
    main()
