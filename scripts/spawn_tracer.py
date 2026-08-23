"""
spawn_tracer.py — OctopusTracer spawn daemon (single-instance, change-aware).

Loads SambaOrchestrator from checkpoint, creates a CAIRRN-bound TracerDaemon,
and runs the gardening loop autonomously — printing live spawn events,
arm scores, CAIRRN hub state, and sucker growth to the console.

Single-instance guarantee
─────────────────────────
An exclusive file-lock on /tmp/samba_octopus.lock is acquired at startup.
Any subsequent launch will detect the lock and exit immediately with a clear
message.  The lock is released automatically on exit or crash — no stale PID
files to clean up manually.

Refresh triggers
─────────────────
Instead of a dumb fixed-interval sleep, the daemon uses a two-level timer:

  fast poll  (--poll-interval, default 5s)
      Wakes every N seconds and checks whether any vault file has been
      modified (mtime scan on the watched paths).  Only triggers a full
      re-encode + tracer cycle when:
        (a) at least one file changed, OR
        (b) time since last cycle ≥ --max-interval (default 300s)

  This gives near-real-time response to vault edits while avoiding
  expensive re-encoding when nothing has changed.

Usage:
    micromamba run -n spot python spawn_tracer.py
    micromamba run -n spot python spawn_tracer.py --checkpoint checkpoints/best.pt
    micromamba run -n spot python spawn_tracer.py --poll-interval 5 --max-interval 300
    micromamba run -n spot python spawn_tracer.py --dry-run
    micromamba run -n spot python spawn_tracer.py --once

Options:
    --checkpoint PATH    Model checkpoint (default: auto-detect best.pt)
    --config PATH        Config file (default: config/config.yaml)
    --poll-interval N    Seconds between vault-change polls (default: 5)
    --max-interval N     Force a cycle after at most N seconds (default: 300)
    --dry-run            Print actions without writing to vault
    --once               Run one cycle and exit
    --fast-embed         Use raw BERT embeddings instead of full GNN pass
    --log-level LEVEL    DEBUG | INFO | WARNING (default: INFO)
    --lock-file PATH     PID lock file (default: /tmp/samba_octopus.lock)
"""
import argparse
import fcntl
import glob
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional, Set

import torch
import yaml

# Shared IPC files — daemon writes state here; MCP tools read/write these.
_CAIRRN_STATE_FILE = "/tmp/samba_cairrn_state.json"
_CAIRRN_CMD_FILE   = "/tmp/samba_cairrn_cmds.json"

# ──────────────────────────────────────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────────────────────────────────────

def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger("spawn_tracer")


# ──────────────────────────────────────────────────────────────────────────────
# Pretty printer
# ──────────────────────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 20, char: str = "█") -> str:
    filled = int(round(value * width))
    return char * filled + "░" * (width - filled)


def _print_cycle_header(cycle: int, n_nodes: int) -> None:
    print(f"\n{'─'*72}")
    print(f"  OCTOPUS TRACER  cycle={cycle:04d}  nodes={n_nodes}")
    print(f"{'─'*72}")


def _print_cairrn(cairrn) -> None:
    print("  CAIRRN hubs:")
    for hub, state in cairrn.hub_state().items():
        coh   = state["coherence"]
        tau   = state.get("tau", "?")
        flag  = "✓" if state["coherent"] else "⚠ INCOHERENT"
        bar   = _bar(coh)
        print(f"    {hub:<16} coh={coh:.3f} [{bar}] τ={tau:<5} shard={state['shard']} {flag}")
    idx = cairrn.index_state()
    print(f"  Harmonic index: {[f'{v:+.3f}' for v in idx]}")


def _print_summary(summary, cycle: int) -> None:
    w = summary.write_gated
    gate_str = "WRITE  ✓" if w else "READ-ONLY ✗"
    print(f"\n  Tracers live: {summary.active_tracers}  "
          f"spawned: {summary.spawned_this_cycle}  "
          f"culled: {summary.culled_this_cycle}  "
          f"gate: {gate_str}")
    if summary.spawn_conditions:
        print(f"  Spawn triggers: {summary.spawn_conditions}")
    if summary.total_suckers:
        total = sum(summary.total_suckers.values())
        print(f"  Suckers alive:  {total}  {dict(summary.total_suckers)}")

    if w:
        print("\n  Arm scores (mean across write-gated swarm):")
        arms = [
            ("Prune",     summary.aggregated_prune),
            ("Resurface", summary.aggregated_resurface),
            ("Sprout",    summary.aggregated_sprout),
            ("Rank",      summary.aggregated_rank),
        ]
        for name, scores in arms:
            if scores is not None:
                top3 = torch.topk(scores, k=min(3, scores.size(0)))
                vals = [f"{v:.3f}" for v in top3.values.tolist()]
                idxs = top3.indices.tolist()
                print(f"    {name:<10} top-3 nodes={idxs}  scores={vals}")

        if summary.aggregated_graft is not None:
            g = summary.aggregated_graft
            nonzero = (g > 0.5).sum().item()
            print(f"    Graft      candidate edges (>0.5): {int(nonzero)}")

        if summary.aggregated_cluster is not None:
            c = summary.aggregated_cluster
            dominant = c.argmax(dim=-1)
            counts = [(dominant == k).sum().item() for k in range(c.size(1))]
            top_clusters = sorted(enumerate(counts), key=lambda x: -x[1])[:4]
            print(f"    Cluster    {[(f'C{k}', n) for k,n in top_clusters]}")
    else:
        print("  [Coherence gate open — arms in read-only mode this cycle]")


# ──────────────────────────────────────────────────────────────────────────────
# Pericles Watchdog — cycle health monitor
# ──────────────────────────────────────────────────────────────────────────────

class PericlesWatchdog:
    """
    Named after the Athenian strategos, Pericles keeps watch over the
    OctopusTracer daemon and intervenes when things go wrong.

    Tracks four health signals each cycle:

        cycle_time      — wall-clock seconds per cycle; warns on slow cycles
        crash_streak    — consecutive failed cycles; raises after max_crash_streak
        readonly_streak — consecutive write-blocked cycles (swarm coma)
        harmonic_drift  — peak absolute change in CAIRRN harmonic index per cycle

    Writes a plaintext heartbeat each cycle to two locations:
        heartbeat_path        — /tmp file for cron/launchd/Grafana
        agent-log/pericles-heartbeat.txt — vault-visible permanent record

    CAIRRN-AWARE enforcement (when mycelial_net is provided):
        drift ≥ drift_spore_threshold  → fires a spore through agent-context hub
                                         to register instability in the mycelial graph
        readonly_streak ≥ max          → calls mycelial_net.decay_all() to release
                                         dormant hyphae and break coherence deadlock

    Args:
        cycle_timeout_s:       warn if a cycle exceeds this many seconds
        max_crash_streak:      raise RuntimeError after this many consecutive failures
        max_readonly_streak:   warn (but don't raise) after this many read-only cycles
        heartbeat_path:        /tmp file path for heartbeat status record
        rolling_window:        number of recent cycles to keep for avg cycle time
        mycelial_net:          optional MycelialNetwork — enables CAIRRN-aware enforcement
        drift_spore_threshold: harmonic drift above which a spore fires (default 0.20)
    """

    def __init__(
        self,
        cycle_timeout_s: float = 120.0,
        max_crash_streak: int  = 5,
        max_readonly_streak: int = 15,
        heartbeat_path: str = "/tmp/samba_octopus.heartbeat",
        rolling_window: int = 20,
        mycelial_net=None,
        drift_spore_threshold: float = 0.20,
    ) -> None:
        self.cycle_timeout_s      = cycle_timeout_s
        self.max_crash_streak     = max_crash_streak
        self.max_readonly_streak  = max_readonly_streak
        self.heartbeat_path       = heartbeat_path
        self.rolling_window       = rolling_window
        self._mycelial            = mycelial_net
        self.drift_spore_threshold = drift_spore_threshold

        self._crash_streak:    int   = 0
        self._readonly_streak: int   = 0
        self._cycle_times:     list  = []
        self._prev_index:      list  = []   # last CAIRRN harmonic index snapshot
        self._cycle_start:     float = 0.0
        self._total_cycles:    int   = 0
        self._vault_hb_path:   Optional[str] = None   # resolved lazily

    # ── public interface ──────────────────────────────────────────────────────

    def begin(self) -> None:
        """Call at the start of each cycle."""
        self._cycle_start = time.time()

    def end(
        self,
        summary=None,
        crashed: bool = False,
        cairrn=None,
    ) -> None:
        """
        Call at the end of each cycle (whether it succeeded or failed).

        Args:
            summary:  TracerSummary from daemon.run_once() (None on crash).
            crashed:  True if the cycle raised an exception.
            cairrn:   CairnBridge instance for harmonic index drift tracking.
        """
        elapsed = time.time() - self._cycle_start
        self._total_cycles += 1
        self._cycle_times.append(elapsed)
        if len(self._cycle_times) > self.rolling_window:
            self._cycle_times.pop(0)

        # ── crash streak ──────────────────────────────────────────────────────
        if crashed:
            self._crash_streak += 1
            logger.warning(
                "Pericles: cycle failed (streak=%d / max=%d)",
                self._crash_streak, self.max_crash_streak,
            )
        else:
            self._crash_streak = 0

        # ── read-only streak (swarm coma) ─────────────────────────────────────
        if summary is not None:
            if not summary.write_gated:
                self._readonly_streak += 1
            else:
                self._readonly_streak = 0

        # ── slow cycle warning ────────────────────────────────────────────────
        if elapsed > self.cycle_timeout_s:
            logger.warning(
                "Pericles: slow cycle %.1fs (limit %.1fs)",
                elapsed, self.cycle_timeout_s,
            )

        # ── harmonic drift ────────────────────────────────────────────────────
        drift = 0.0
        if cairrn is not None:
            cur_index = cairrn.index_state()
            if self._prev_index:
                drift = max(abs(a - b) for a, b in zip(cur_index, self._prev_index))
            self._prev_index = list(cur_index)

        # ── heartbeat file ────────────────────────────────────────────────────
        self._write_heartbeat(elapsed, crashed, drift)

        # ── escalations ──────────────────────────────────────────────────────
        if self._crash_streak >= self.max_crash_streak:
            raise RuntimeError(
                f"Pericles: crash loop — {self._crash_streak} consecutive failures. "
                f"Check logs and restart manually."
            )
        if self._readonly_streak >= self.max_readonly_streak:
            logger.warning(
                "Pericles: swarm coma — %d consecutive read-only cycles. "
                "Consider restarting or reducing cull_after_readonly_ticks.",
                self._readonly_streak,
            )
            # ── Active recovery: release dormant hyphae to break coherence deadlock
            if self._mycelial is not None:
                try:
                    decay_result = self._mycelial.decay_all()
                    logger.info(
                        "Pericles [coma recovery]: mycelial decay fired — "
                        "active=%d  went_dormant=%d",
                        decay_result.get("active_after_decay", 0),
                        decay_result.get("went_dormant", 0),
                    )
                except Exception as exc:
                    logger.warning("Pericles: mycelial coma recovery failed: %s", exc)

        # ── CAIRRN-aware: drift spore through agent-context hub ───────────────
        if self._mycelial is not None and drift >= self.drift_spore_threshold:
            try:
                self._mycelial.spore(
                    query=f"CAIRRN harmonic instability drift={drift:.4f}",
                    hub="agent-context",
                )
                logger.info(
                    "Pericles [drift spore]: harmonic drift=%.4f fired agent-context spore",
                    drift,
                )
            except Exception as exc:
                logger.warning("Pericles: drift spore failed: %s", exc)

    def status_line(self) -> str:
        """One-line health summary for console output."""
        avg = sum(self._cycle_times) / len(self._cycle_times) if self._cycle_times else 0.0
        return (
            f"Pericles  cycles={self._total_cycles}  "
            f"avg={avg:.1f}s  "
            f"crash_streak={self._crash_streak}  "
            f"readonly_streak={self._readonly_streak}"
        )

    # ── internals ─────────────────────────────────────────────────────────────

    def _resolve_vault_hb_path(self) -> Optional[str]:
        """Lazily resolve agent-log/pericles-heartbeat.txt inside the vault."""
        if self._vault_hb_path is not None:
            return self._vault_hb_path
        try:
            from engine.vault_writer import _load_vault_path
            vault_root = _load_vault_path()
            log_dir = vault_root / "agent-log"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._vault_hb_path = str(log_dir / "pericles-heartbeat.txt")
        except Exception:
            pass
        return self._vault_hb_path

    def _write_heartbeat(self, last_s: float, crashed: bool, drift: float) -> None:
        avg = sum(self._cycle_times) / len(self._cycle_times) if self._cycle_times else 0.0
        status = "CRASHED" if crashed else ("COMA" if self._readonly_streak >= self.max_readonly_streak else "READONLY" if self._readonly_streak > 0 else "OK")
        lines = [
            f"pid={os.getpid()}",
            f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            f"status={status}",
            f"total_cycles={self._total_cycles}",
            f"last_cycle_s={last_s:.2f}",
            f"avg_cycle_s={avg:.2f}",
            f"crash_streak={self._crash_streak}",
            f"readonly_streak={self._readonly_streak}",
            f"harmonic_drift={drift:.4f}",
            f"drift_spore_threshold={self.drift_spore_threshold:.4f}",
            f"mycelial_active={'yes' if self._mycelial is not None else 'no'}",
        ]
        content = "\n".join(lines) + "\n"

        # /tmp — fast, for cron/launchd/Grafana
        try:
            with open(self.heartbeat_path, "w") as fh:
                fh.write(content)
        except OSError:
            pass

        # vault — permanent, visible in Obsidian graph
        vault_path = self._resolve_vault_hb_path()
        if vault_path:
            tmp = vault_path + ".tmp"
            try:
                with open(tmp, "w") as fh:
                    fh.write(content)
                os.replace(tmp, vault_path)
            except OSError:
                pass


# ──────────────────────────────────────────────────────────────────────────────
# Vault write loop
# ──────────────────────────────────────────────────────────────────────────────

def _apply_tracer_writes(summary, idx_map: dict, writer, args) -> None:
    """
    Translate aggregated arm outputs into vault writes.

    Only runs when the swarm is write-gated (coherence ≥ 0.50) and idx_map
    is non-empty.  All writes are skipped if args.dry_run is True (VaultWriter
    handles that internally, but we log the gate skip here too).

    Arms handled:
        Graft     → VaultWriter.append_links()   (missing wikilinks)
        Resurface → VaultWriter.write_agent_note() (buried high-value notes)
        Sprout    → VaultWriter.write_agent_note() (structural gap candidates)
        Prune     → VaultWriter.write_agent_note() (deletion candidates, human-review)

    Note: aggregated_tag and aggregated_merge are not yet on TracerSummary
    (see gap #2) — add them here once that dataclass field is filled in.
    """
    if not summary.write_gated:
        return
    if not idx_map:
        logger.debug("_apply_tracer_writes: idx_map empty — skipping writes")
        return

    import torch

    # ── Graft: append missing wikilinks ──────────────────────────────────────
    if summary.aggregated_graft is not None:
        graft = summary.aggregated_graft                        # (N, N) upper-tri
        above = (graft > args.graft_threshold).nonzero(as_tuple=False)
        if above.size(0) > 0:
            scores = graft[above[:, 0], above[:, 1]]
            order  = scores.argsort(descending=True)[: args.top_k_graft]
            written = 0
            for k in order.tolist():
                i, j   = above[k, 0].item(), above[k, 1].item()
                ni, nj = idx_map.get(i), idx_map.get(j)
                if ni and nj:
                    writer.append_links(nj["path"], [{"title": ni["title"]}])
                    writer.append_links(ni["path"], [{"title": nj["title"]}])
                    written += 1
            if written:
                logger.info("Graft: wrote %d link pair(s) (threshold=%.2f)",
                            written, args.graft_threshold)

    # ── Resurface: log buried high-value notes ────────────────────────────────
    if summary.aggregated_resurface is not None:
        resurface  = summary.aggregated_resurface               # (N,)
        above_mask = resurface > args.resurface_threshold
        if above_mask.any():
            n_top     = min(args.top_k_resurface, int(above_mask.sum().item()))
            top_idxs  = resurface.topk(n_top).indices.tolist()
            candidates = [idx_map[i]["title"] for i in top_idxs if i in idx_map]
            if candidates:
                body = (
                    "OctopusTracer identified these notes as semantically rich but "
                    "structurally peripheral. They may benefit from additional inbound links.\n\n"
                    + "\n".join(f"- [[{t}]]" for t in candidates)
                )
                writer.write_agent_note(
                    title="Resurface Candidates",
                    body=body,
                    links=candidates,
                    zone="agent-log",
                )
                logger.info("Resurface: logged %d candidate(s)", len(candidates))

    # ── Sprout: flag structural gaps for new connective tissue ────────────────
    if summary.aggregated_sprout is not None:
        sprout     = summary.aggregated_sprout                  # (N,)
        above_mask = sprout > args.sprout_threshold
        if above_mask.any():
            n_top     = min(args.top_k_sprout, int(above_mask.sum().item()))
            top_idxs  = sprout.topk(n_top).indices.tolist()
            candidates = [idx_map[i]["title"] for i in top_idxs if i in idx_map]
            if candidates:
                body = (
                    "OctopusTracer identified these nodes as having high structural gap "
                    "pressure — their neighbourhoods are sparse and semantically "
                    "underrepresented. New connective notes or bridge links are recommended.\n\n"
                    + "\n".join(f"- [[{t}]]" for t in candidates)
                )
                writer.write_agent_note(
                    title="Sprout Candidates",
                    body=body,
                    links=candidates,
                    zone="agent-log",
                )
                logger.info("Sprout: logged %d gap candidate(s)", len(candidates))

    # ── Prune: log deletion candidates for human review ───────────────────────
    if summary.aggregated_prune is not None:
        prune      = summary.aggregated_prune                   # (N,)
        above_mask = prune > args.prune_threshold
        if above_mask.any():
            n_top     = min(args.top_k_prune, int(above_mask.sum().item()))
            top_idxs  = prune.topk(n_top).indices.tolist()
            candidates = [
                (idx_map[i]["title"], round(prune[i].item(), 3))
                for i in top_idxs if i in idx_map
            ]
            if candidates:
                body = (
                    "OctopusTracer flagged these notes as prune candidates "
                    "(orphan / stale / low-connectivity). Human review recommended — "
                    "no autonomous deletion is performed.\n\n"
                    + "\n".join(f"- [[{t}]]  score={s:.3f}" for t, s in candidates)
                )
                writer.write_agent_note(
                    title="Prune Candidates",
                    body=body,
                    links=[t for t, _ in candidates],
                    zone="agent-log",
                )
                logger.info("Prune: flagged %d candidate(s) for review", len(candidates))

    # ── Merge: log near-duplicate pairs (Ana-Chi weighted, CODE hub) ──────────
    # aggregated_merge is produced by Ana-Chi dual-arm smoothing in TracerDaemon.
    # Merge candidates are emitted as agent-log review notes only — no autonomous
    # consolidation. Tag is omitted here until a tag vocabulary is defined (gap 4).
    if getattr(summary, "aggregated_merge", None) is not None:
        merge      = summary.aggregated_merge                   # (N, N) upper-tri
        above      = (merge > args.merge_threshold).nonzero(as_tuple=False)
        if above.size(0) > 0:
            scores = merge[above[:, 0], above[:, 1]]
            order  = scores.argsort(descending=True)[: args.top_k_merge]
            pairs: list = []
            for k in order.tolist():
                i, j   = above[k, 0].item(), above[k, 1].item()
                ni, nj = idx_map.get(i), idx_map.get(j)
                if ni and nj:
                    pairs.append((ni["title"], nj["title"], round(merge[i, j].item(), 3)))
            if pairs:
                body = (
                    "OctopusTracer (Ana-Chi / CODE hub) identified these note pairs "
                    "as near-duplicates. Human review recommended before consolidation.\n\n"
                    + "\n".join(f"- [[{a}]] ↔ [[{b}]]  score={s:.3f}" for a, b, s in pairs)
                )
                all_titles = list(dict.fromkeys(t for p in pairs for t in p[:2]))
                writer.write_agent_note(
                    title="Merge Candidates",
                    body=body,
                    links=all_titles,
                    zone="agent-log",
                )
                logger.info("Merge: flagged %d pair(s) (Ana-Chi / CODE hub)", len(pairs))


# ──────────────────────────────────────────────────────────────────────────────
# CAIRRN IPC — state broadcast + command queue
# ──────────────────────────────────────────────────────────────────────────────

def _broadcast_cairrn_state(cairrn, cycle: int, n_nodes: int) -> None:
    """
    Write the daemon's live CAIRRN state to /tmp/samba_cairrn_state.json so
    the MCP server and external tools can read it without IPC.

    Atomic write via a .tmp sidecar to prevent torn reads.
    """
    try:
        payload = {
            "pid":       os.getpid(),
            "cycle":     cycle,
            "n_nodes":   n_nodes,
            "ts":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hubs":      cairrn.hub_state(),
            "index":     cairrn.index_state(),
            "global_coherence": round(cairrn.global_coherence(), 4),
            "global_z":  round(cairrn.global_z_awareness(), 4),
            "spawn_signals": {k: round(v, 4) for k, v in cairrn.spawn_signals().items()},
            "z_signals": {k: round(v, 4) for k, v in cairrn.z_awareness_signals().items()},
        }
        tmp = _CAIRRN_STATE_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, _CAIRRN_STATE_FILE)
    except Exception as e:
        logger.debug("CAIRRN state broadcast failed: %s", e)


def _drain_cairrn_cmds(cairrn) -> None:
    """
    Drain the CAIRRN command queue written by MCP tools.

    Each command is a dict: {"hub": str, "value": float}.
    Commands are injected into the bridge via CairnBridge.step(), then the
    queue file is deleted so commands are consumed exactly once.
    """
    if not os.path.exists(_CAIRRN_CMD_FILE):
        return
    try:
        with open(_CAIRRN_CMD_FILE) as fh:
            cmds = json.load(fh)
        os.remove(_CAIRRN_CMD_FILE)
        if not isinstance(cmds, list):
            cmds = [cmds]
        for cmd in cmds:
            hub   = cmd.get("hub", "HOME")
            value = float(cmd.get("value", 0.5))
            try:
                cairrn.step(hub, value)
                logger.info("CAIRRN inject from MCP: hub=%s value=%.4f", hub, value)
            except Exception as e:
                logger.warning("CAIRRN inject failed (hub=%s): %s", hub, e)
    except Exception as e:
        logger.debug("CAIRRN command drain failed: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Single-instance lock
# ──────────────────────────────────────────────────────────────────────────────

_lock_fh = None   # global so it stays open (lock released on close/GC)


def _acquire_lock(lock_path: str) -> bool:
    """
    Attempt to acquire an exclusive non-blocking flock on lock_path.

    Returns True on success, False if another instance holds the lock.
    Writes our PID into the file for inspection with `cat <lock_path>`.
    """
    global _lock_fh
    try:
        _lock_fh = open(lock_path, "w")
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
        return True
    except (BlockingIOError, OSError):
        if _lock_fh:
            _lock_fh.close()
            _lock_fh = None
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Change-detection scanner
# ──────────────────────────────────────────────────────────────────────────────

def _vault_mtime(roots) -> float:
    """
    Walk the watched roots and return the most recent file mtime found.
    Fast O(N) scan — doesn't open any files, just checks stat().
    Skips binary / excluded extensions to match crawler behaviour.
    """
    _SKIP_SUFFIXES = {
        ".pyc", ".pyo", ".so", ".dylib",
        ".png", ".jpg", ".gif", ".pdf",
        ".pt", ".pth", ".bin", ".lock", ".db",
        ".mp3", ".mp4",
    }
    _SKIP_DIRS = {
        "node_modules", "__pycache__", ".git", ".venv", "venv",
        "site-packages", ".cache", "Caches", "Library",
        # Cursor / IDE state dirs — written constantly, not vault content
        ".cursor", "agent-transcripts", "terminals", "mcps",
    }
    latest = 0.0
    for root in roots:
        root = str(Path(root).expanduser().resolve())
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in _SKIP_SUFFIXES:
                    continue
                try:
                    mt = os.stat(os.path.join(dirpath, fname)).st_mtime
                    if mt > latest:
                        latest = mt
                except OSError:
                    pass
    return latest


def run(args) -> None:
    _setup_logging(args.log_level)

    # ── Single-instance lock ──────────────────────────────────────────────────
    if not args.once:
        if not _acquire_lock(args.lock_file):
            print(
                f"[spawn_tracer] Another instance is already running.\n"
                f"  Lock held by PID in: {args.lock_file}\n"
                f"  Kill it with:  kill $(cat {args.lock_file})\n"
                f"  Or use --once to run a single cycle without locking."
            )
            sys.exit(0)
        logger.info("Lock acquired: %s  (PID %d)", args.lock_file, os.getpid())

    project_root = Path(__file__).parent.resolve()
    config_path  = args.config or str(project_root / "config" / "config.yaml")

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Watched roots for change-detection (use crawler roots from config)
    watch_roots = cfg.get("crawler", {}).get("roots", ["~/"])

    # ── Auto-detect checkpoint ────────────────────────────────────────────────
    ckpt = args.checkpoint
    if ckpt is None:
        ckpt_dir = project_root / "checkpoints"
        best = ckpt_dir / "best.pt"
        if best.exists():
            ckpt = str(best)
        else:
            candidates = sorted(glob.glob(str(ckpt_dir / "epoch_*.pt")))
            ckpt = candidates[-1] if candidates else None
    if ckpt is None:
        logger.error("No checkpoint found — run: python train.py --stage finetune")
        sys.exit(1)

    logger.info("Checkpoint:    %s", ckpt)
    logger.info("Config:        %s", config_path)
    logger.info("Poll interval: %ds  Max interval: %ds  dry_run=%s",
                args.poll_interval, args.max_interval, args.dry_run)

    # ── Load orchestrator ─────────────────────────────────────────────────────
    from inference import SambaOrchestrator
    logger.info("Loading SambaOrchestrator…")
    orch = SambaOrchestrator(
        checkpoint_path=ckpt,
        config_path=config_path,
        lazy_embed=args.fast_embed,
    )
    n_nodes = orch._h.size(0) if orch._h is not None else 0
    logger.info("Graph: %d nodes  (fast_embed=%s)", n_nodes, args.fast_embed)

    # ── Build TracerDaemon ────────────────────────────────────────────────────
    from engine.tracer_daemon import TracerDaemon
    logger.info("Spawning TracerDaemon (CAIRRN-bound, soft-edge)…")
    daemon = TracerDaemon.from_config(cfg)

    # ── VaultWriter ───────────────────────────────────────────────────────────
    from engine.vault_writer import VaultWriter
    writer = VaultWriter(dry_run=args.dry_run)
    logger.info("VaultWriter ready (dry_run=%s  vault=%s)", args.dry_run, writer.vault_path)

    # ── BERT projection weight for sucker warm-start ──────────────────────────
    bert_proj_weight = None
    if hasattr(orch.model, "encoder") and hasattr(orch.model.encoder, "proj"):
        bert_proj_weight = orch.model.encoder.proj.weight.detach()

    # ── MycelialNetwork — optional, enables CAIRRN-aware Pericles enforcement ──
    _mycelial = None
    if not args.no_mycelial:
        try:
            from engine.mycelial import MycelialNetwork
            _mycelial = MycelialNetwork(orch)
            logger.info("MycelialNetwork attached to Pericles watchdog")
        except Exception as e:
            logger.warning("MycelialNetwork unavailable — Pericles enforcement disabled: %s", e)

    # ── Pericles Watchdog ─────────────────────────────────────────────────────
    pericles = PericlesWatchdog(
        cycle_timeout_s    = args.watchdog_timeout,
        max_crash_streak   = args.watchdog_max_crashes,
        max_readonly_streak = args.watchdog_max_readonly,
        heartbeat_path     = args.watchdog_heartbeat,
        mycelial_net       = _mycelial,
        drift_spore_threshold = args.watchdog_drift_spore,
    )
    logger.info(
        "Pericles watchdog armed (timeout=%.0fs  max_crashes=%d  max_readonly=%d  "
        "drift_spore=%.2f  mycelial=%s  hb=%s)",
        args.watchdog_timeout, args.watchdog_max_crashes,
        args.watchdog_max_readonly, args.watchdog_drift_spore,
        "active" if _mycelial is not None else "disabled",
        args.watchdog_heartbeat,
    )

    print("\n" + "="*72)
    print("  OCTOPUS TRACER  —  autonomous vault gardening")
    print(f"  soft_edge_mode={daemon.soft_edge_mode}  cairrn_bound={daemon.cairrn_bound}")
    print(f"  max_tracers={daemon.max_tracers}  tau_cairrn={daemon.tau_cairrn}")
    print(f"  spawn_threshold={daemon.spawn_threshold}  dry_run={args.dry_run}")
    print(f"  poll={args.poll_interval}s  min_gap={args.min_cycle_gap}s  "
          f"max_interval={args.max_interval}s  lock={args.lock_file}")
    print(f"  pericles timeout={args.watchdog_timeout}s  heartbeat={args.watchdog_heartbeat}")
    print("="*72)

    cycle          = 0
    last_mtime     = _vault_mtime(watch_roots)  # baseline after init
    last_cycle_ts  = 0.0                         # epoch time of last full cycle

    def _should_run(now: float) -> tuple:
        """
        Returns (should_run: bool, reason: str).

        Triggers when:
          (a) a vault file has changed AND min_cycle_gap has elapsed
          (b) more than max_interval seconds have elapsed (heartbeat)
        The min_cycle_gap debounce prevents re-encoding during write storms
        (e.g. continuous agent-transcript writes from the IDE).
        """
        nonlocal last_mtime
        elapsed = now - last_cycle_ts
        if elapsed < args.min_cycle_gap:
            return False, ""
        current_mtime = _vault_mtime(watch_roots)
        if current_mtime > last_mtime:
            last_mtime = current_mtime
            return True, "vault_change"
        if elapsed >= args.max_interval:
            return True, "max_interval"
        return False, ""

    while True:
        # ── First cycle always runs immediately ───────────────────────────────
        if cycle == 0:
            trigger = "cold_start"
        else:
            # Poll loop — wake every poll_interval and check for triggers
            trigger = ""
            while not trigger:
                try:
                    time.sleep(args.poll_interval)
                except KeyboardInterrupt:
                    print("\n[Interrupted] Shutting down octopus tracer.")
                    return
                fire, trigger = _should_run(time.time())
                if not fire:
                    trigger = ""

        cycle += 1
        last_cycle_ts = time.time()

        # ── Refresh orchestrator on cycles > 1 ───────────────────────────────
        if cycle > 1:
            logger.info("Trigger: %s — refreshing graph…", trigger)
            try:
                orch.refresh()
            except Exception as e:
                logger.warning("Orchestrator refresh failed: %s", e)

        H = orch.node_embeddings(fast=args.fast_embed)
        if H is None or H.size(0) == 0:
            logger.warning("No nodes in graph — waiting for vault data…")
            continue
        logger.info("H: %s  device=%s  trigger=%s", tuple(H.shape), H.device, trigger)

        # ── Snapshot ─────────────────────────────────────────────────────────
        snap = {}
        try:
            if args.fast_embed:
                snap = orch.graph_snapshot()
            else:
                orch.topo.build()
                snap = orch.topo.snapshot()
        except Exception as e:
            logger.debug("Snapshot failed: %s", e)

        # ── Drain MCP inject commands queued since last cycle ─────────────────
        _drain_cairrn_cmds(daemon.cairrn)

        _print_cycle_header(cycle, H.size(0))
        print(f"  Trigger: {trigger}")
        _print_cairrn(daemon.cairrn)

        # ── Node index → note path mapping (rebuild after each refresh) ─────────
        idx_map: dict = {}
        try:
            idx_map = orch.node_index_map()
        except Exception as e:
            logger.debug("node_index_map failed: %s", e)

        # ── Run tracer cycle (Pericles-monitored) ─────────────────────────────
        summary = None
        pericles.begin()
        try:
            summary = daemon.run_once(
                snapshot=snap,
                H=H,
                bert_proj_weight=bert_proj_weight,
            )
            _print_summary(summary, cycle)
            _apply_tracer_writes(summary, idx_map, writer, args)
            pericles.end(summary=summary, crashed=False, cairrn=daemon.cairrn)
            _broadcast_cairrn_state(daemon.cairrn, cycle, H.size(0))
        except RuntimeError as e:
            # Pericles crash-loop escalation — re-raise to kill the daemon
            pericles.end(summary=None, crashed=True, cairrn=daemon.cairrn)
            raise
        except Exception as e:
            logger.error("TracerDaemon cycle failed: %s", e, exc_info=True)
            pericles.end(summary=None, crashed=True, cairrn=daemon.cairrn)

        print(f"  {pericles.status_line()}")

        if args.once:
            print("\n[--once] Single cycle complete. Exiting.")
            break

        print(f"\n  Polling every {args.poll_interval}s "
              f"(min gap {args.min_cycle_gap}s, max {args.max_interval}s)…")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OctopusTracer — autonomous Obsidian vault gardening daemon",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--checkpoint",     default=None, help="Model checkpoint path")
    p.add_argument("--config",         default=None, help="config.yaml path")
    p.add_argument("--poll-interval",  type=int, default=5,
                   help="Seconds between vault-change polls")
    p.add_argument("--min-cycle-gap",  type=int, default=60,
                   help="Minimum seconds between full re-encode cycles (debounce)")
    p.add_argument("--max-interval",   type=int, default=300,
                   help="Force a cycle after at most N seconds even with no changes")
    p.add_argument("--dry-run",        action="store_true", help="Do not write to vault")
    p.add_argument("--once",           action="store_true", help="Run one cycle and exit")
    p.add_argument("--fast-embed",     action="store_true",
                   help="Use raw BERT embeddings instead of full GNN pass")
    p.add_argument("--log-level",      default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--lock-file",      default="/tmp/samba_octopus.lock",
                   help="Exclusive lock file path (single-instance guard)")

    # ── Write thresholds ──────────────────────────────────────────────────────
    p.add_argument("--graft-threshold",    type=float, default=0.75,
                   help="Graft arm score above which a missing link is written (default: 0.75)")
    p.add_argument("--resurface-threshold", type=float, default=0.75,
                   help="Resurface arm score above which a note is logged as buried (default: 0.75)")
    p.add_argument("--sprout-threshold",   type=float, default=0.80,
                   help="Sprout arm score above which a structural gap is logged (default: 0.80)")
    p.add_argument("--prune-threshold",    type=float, default=0.85,
                   help="Prune arm score above which a node is flagged for review (default: 0.85)")
    p.add_argument("--top-k-graft",        type=int,   default=10,
                   help="Max link pairs written per cycle by Graft arm (default: 10)")
    p.add_argument("--top-k-resurface",    type=int,   default=5,
                   help="Max resurface candidates logged per cycle (default: 5)")
    p.add_argument("--top-k-sprout",       type=int,   default=3,
                   help="Max sprout candidates logged per cycle (default: 3)")
    p.add_argument("--top-k-prune",        type=int,   default=5,
                   help="Max prune candidates flagged per cycle (default: 5)")
    p.add_argument("--merge-threshold",    type=float, default=0.80,
                   help="Merge arm score (Ana-Chi/CODE) above which pair is flagged (default: 0.80)")
    p.add_argument("--top-k-merge",        type=int,   default=5,
                   help="Max merge candidate pairs logged per cycle (default: 5)")

    # ── Pericles watchdog ─────────────────────────────────────────────────────
    p.add_argument("--watchdog-timeout",      type=float, default=120.0,
                   help="Seconds per cycle above which Pericles warns (default: 120)")
    p.add_argument("--watchdog-max-crashes",  type=int,   default=5,
                   help="Consecutive failed cycles before Pericles raises (default: 5)")
    p.add_argument("--watchdog-max-readonly", type=int,   default=15,
                   help="Consecutive read-only cycles before Pericles warns of swarm coma (default: 15)")
    p.add_argument("--watchdog-heartbeat",    default="/tmp/samba_octopus.heartbeat",
                   help="Path for Pericles /tmp heartbeat file (vault copy always written)")
    p.add_argument("--watchdog-drift-spore",  type=float, default=0.20,
                   help="Harmonic drift above which Pericles fires an agent-context spore (default 0.20)")
    p.add_argument("--no-mycelial",           action="store_true",
                   help="Disable MycelialNetwork attachment to Pericles watchdog")

    return p.parse_args()


if __name__ == "__main__":
    run(_parse())
