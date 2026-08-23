"""
MCP Obsidian Bridge — Live Vault Sync Daemon
Polls the Obsidian vault for changes and triggers adaptive retraining
when topology shifts are detected. Also exposes the SambaOrchestrator
as a simple JSON-RPC-compatible interface for MCP tool calls.

Run alongside your Obsidian instance:
    python mcp_bridge.py --checkpoint checkpoints/best.pt

MCP tools exposed:
    samba/find_related      — related note retrieval
    samba/suggest_links     — orphan link suggestions
    samba/get_clusters      — topic cluster view
    samba/route_query       — free-text query routing
    samba/refresh           — force re-encode + rebuild

    tracer/status           — live tracer swarm status + CAIRRN hub state
    tracer/cairrn           — full CAIRRN harmonic index state
    tracer/scores           — latest aggregated arm scores (prune/graft/sprout/…)
"""
import json
import logging
import os
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import torch
import yaml

from inference import SambaOrchestrator
from phi.gnn.coherence import CoherenceWeightSchedule
from phi.utils.replay import ReplayBuffer, prefill_buffer_synthetic
from phi.utils.perpetual import PerpetualTrainer, EMAModel
from engine.tracer_daemon import TracerDaemon, TracerSummary

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("mcp_bridge")


# ──────────────────────────────────────────────────────────────────────────────
# Vault change watcher
# ──────────────────────────────────────────────────────────────────────────────

class VaultWatcher(threading.Thread):
    """Background thread that polls for vault changes and triggers refresh."""

    def __init__(
        self,
        orchestrator: SambaOrchestrator,
        poll_interval: int = 30,
    ) -> None:
        super().__init__(daemon=True)
        self.orch = orchestrator
        self.poll_interval = poll_interval
        self._stop = threading.Event()

    def run(self) -> None:
        logger.info(f"VaultWatcher started (poll interval: {self.poll_interval}s)")
        while not self._stop.is_set():
            time.sleep(self.poll_interval)
            try:
                new_notes, modified = self.orch.graph.detect_changes()
                if new_notes or modified:
                    logger.info(
                        f"Vault changed: {len(new_notes)} new notes, "
                        f"{len(modified)} modified. Refreshing representations..."
                    )
                    self.orch.refresh()
                    logger.info("Refresh complete.")
            except Exception as e:
                logger.warning(f"VaultWatcher error: {e}")

    def stop(self) -> None:
        self._stop.set()


# ──────────────────────────────────────────────────────────────────────────────
# JSON-RPC-compatible HTTP handler
# ──────────────────────────────────────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):
    orchestrator: SambaOrchestrator = None   # set at server startup
    tracer_daemon: TracerDaemon     = None   # set at server startup
    _latest_summary: TracerSummary  = None   # updated by background tracer thread

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        tool = req.get("tool", "")
        params = req.get("params", {})

        try:
            result = self._dispatch(tool, params)
            self._respond(200, {"result": result})
        except Exception as e:
            logger.error(f"Error in tool {tool}: {e}")
            self._respond(500, {"error": str(e)})

    def _dispatch(self, tool: str, params: Dict[str, Any]) -> Any:
        orch = MCPHandler.orchestrator
        td   = MCPHandler.tracer_daemon

        # ── Samba tools ──────────────────────────────────────────────────────
        if tool == "samba/find_related":
            return orch.find_related(params["note"], params.get("top_k", 10))
        elif tool == "samba/suggest_links":
            return orch.suggest_links(params["note"], params.get("top_k", 5))
        elif tool == "samba/get_clusters":
            return orch.get_clusters()
        elif tool == "samba/route_query":
            return orch.route_query(params["query"], params.get("top_k", 5))
        elif tool == "samba/refresh":
            orch.refresh()
            return {"status": "refreshed", "nodes": orch.graph.num_nodes}

        # ── Tracer tools ─────────────────────────────────────────────────────
        elif tool == "tracer/status":
            if td is None:
                return {"error": "tracer_daemon not initialised"}
            return {
                "active_tracers":  len(td._tracers),
                "cycle":           td._cycle,
                "soft_edge_mode":  td.soft_edge_mode,
                "cairrn_bound":    td.cairrn_bound,
                "cairrn_hubs":     td.cairrn.hub_state(),
                "cairrn_index":    td.cairrn.index_state(),
                "global_coherence": round(td.cairrn.global_coherence(), 4),
                "all_coherent":    td.cairrn.all_coherent(),
            }

        elif tool == "tracer/cairrn":
            if td is None:
                return {"error": "tracer_daemon not initialised"}
            return {
                "hub_state":    td.cairrn.hub_state(),
                "index":        td.cairrn.index_state(),
                "report":       td.cairrn.report(),
                "spawn_signals": td.cairrn.spawn_signals(),
            }

        elif tool == "tracer/scores":
            summary = MCPHandler._latest_summary
            if summary is None:
                return {"status": "no tracer cycle run yet"}
            return {
                "write_gated":     summary.write_gated,
                "active_tracers":  summary.active_tracers,
                "total_suckers":   summary.total_suckers,
                "has_prune":       summary.aggregated_prune is not None,
                "has_graft":       summary.aggregated_graft is not None,
                "spawned_this_cycle": summary.spawned_this_cycle,
                "spawn_conditions":   summary.spawn_conditions,
            }

        else:
            raise ValueError(f"Unknown tool: {tool}")

    def _respond(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--vault_url", default=None)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    poll_interval = cfg["mcp"]["sync_interval_seconds"]

    logger.info("Initializing SambaOrchestrator...")
    orch = SambaOrchestrator(
        checkpoint_path=args.checkpoint,
        config_path=args.config,
        vault_url=args.vault_url,
    )

    # ── Perpetual background training ─────────────────────────────────────
    # The model continues learning even while serving inference requests.
    logger.info("Starting perpetual background trainer...")
    optimizer = torch.optim.AdamW(
        [p for p in orch.model.parameters() if p.requires_grad],
        lr=cfg["training"]["learning_rate"] * 0.1,   # lower LR for online refinement
        weight_decay=cfg["training"]["weight_decay"],
    )

    total_steps = 50_000   # effectively infinite for a daemon
    coh_schedule = CoherenceWeightSchedule(
        alpha=0.10, beta=0.05, gamma=0.08, delta=0.03,
        warmup_frac=0.05, ramp_frac=0.20,
        total_steps=total_steps,
    )

    buffer = ReplayBuffer(capacity=32, recency_decay=0.003, min_vault_frac=0.5)
    prefill_buffer_synthetic(
        buffer, n_snapshots=8,
        hidden_dim=cfg["model"]["gnn"]["hidden_dim"],
        max_neighbors=cfg["walk"]["max_neighbors"],
    )

    device = orch.device
    perpetual = PerpetualTrainer(
        model=orch.model,
        optimizer=optimizer,
        buffer=buffer,
        coh_schedule=coh_schedule,
        device=device,
        gpu_fraction=0.15,       # low fraction — inference takes priority
        checkpoint_every_steps=500,
        checkpoint_dir=cfg["training"]["checkpoint_dir"],
    )
    perpetual.start()
    logger.info("Perpetual trainer running in background (15% GPU fraction)")

    # ── Octopus TracerDaemon ────────────────────────────────────────────────
    logger.info("Initialising OctopusTracer daemon (CAIRRN-bound soft-edge mode)…")
    tracer_daemon = TracerDaemon.from_config(cfg)

    def _tracer_cycle_thread():
        """Background thread: run one tracer cycle after each vault watcher poll."""
        import time as _time
        while True:
            _time.sleep(poll_interval)
            try:
                H = orch._h                    # (N, D) — live cached node embeddings
                snap = {}
                if hasattr(orch, "topo") and orch.topo is not None:
                    orch.topo.build()
                    snap = orch.topo.snapshot()
                bert_w = None
                if hasattr(orch.model, "encoder"):
                    bert_w = orch.model.encoder.proj.weight.detach()
                summary = tracer_daemon.run_once(
                    snapshot=snap,
                    H=H,
                    bert_proj_weight=bert_w,
                )
                MCPHandler._latest_summary = summary
            except Exception as e:
                logger.warning("TracerDaemon cycle error: %s", e)

    _tracer_thread = threading.Thread(target=_tracer_cycle_thread, daemon=True)
    _tracer_thread.start()
    logger.info("OctopusTracer daemon running in background")

    # ── Vault watcher ──────────────────────────────────────────────────────
    watcher = VaultWatcher(orch, poll_interval=poll_interval)
    watcher.start()

    # ── HTTP server ────────────────────────────────────────────────────────
    server = HTTPServer((args.host, args.port), MCPHandler)
    logger.info(f"MCP bridge listening on http://{args.host}:{args.port}")
    logger.info("Available tools: samba/find_related | samba/suggest_links | "
                "samba/get_clusters | samba/route_query | samba/refresh")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        perpetual.stop()
        watcher.stop()
        perpetual.join(timeout=5.0)
        server.server_close()


if __name__ == "__main__":
    main()
