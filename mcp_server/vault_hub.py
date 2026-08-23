"""
VaultHub — backwards enforcement from MCP server into the Obsidian vault.

Data flow
---------
Forward (existing):   vault .md files → PSSPPS retriever → harmonic scorer → MCP tool results
Backwards (this file): MCP tool results → VaultHub.push_*() → vault live-state.md

The vault is the hub.  Every mutating MCP operation writes a snapshot back to
`Spotify-rip/live-state.md`.  Obsidian picks it up immediately (file watcher).
The graph then reflects live server state — the vault stays the canonical record.

Thread safety
-------------
Same pattern as HarmonicIndex and DOMRequestQueue: a single threading.RLock
guards all writes.  Writes are fast (small .md file), so lock contention is
negligible.

Registration
------------
VaultHub is instantiated once at spawn alongside the DOM queue:

    _vault_hub = VaultHub(vault_dir=Path(__file__).parent.parent)  # Spotify-rip/ vault root

Then called inside tool bodies after state-mutating operations:

    _vault_hub.push_harmonic(state_dict)
    _vault_hub.push_sim("double_well_sim", result_dict)
    _vault_hub.push_queue(queue_state_dict)
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# VaultHub
# ---------------------------------------------------------------------------


class VaultHub:
    """
    Writes MCP server state back into the Obsidian vault as live-state.md.

    All push_* methods are thread-safe and fire-and-update: they overwrite
    `live-state.md` with the latest composite snapshot each time they are called.
    """

    LIVE_STATE_FILE = "live-state.md"

    def __init__(self, vault_dir: Path) -> None:
        self._vault_dir = vault_dir.resolve()
        self._lock = threading.RLock()

        # In-memory state pockets — each push_* updates its own pocket, then
        # the whole file is rewritten.  This keeps the note coherent even when
        # different tools fire in quick succession.
        self._harmonic: dict[str, Any] = {}
        self._last_sim: dict[str, Any] = {}
        self._queue: dict[str, Any] = {}
        self._forecast: dict[str, Any] = {}
        self._push_count: int = 0

        # Create the vault dir if it doesn't exist (shouldn't happen, but safe)
        self._vault_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Push methods (called by MCP tools)
    # ------------------------------------------------------------------

    def push_harmonic(self, state: dict[str, Any]) -> None:
        """Push harmonic index state to the vault."""
        with self._lock:
            self._harmonic = state
            self._push_count += 1
            self._write()

    def push_sim(self, tool_name: str, result: dict[str, Any]) -> None:
        """Push the result of a simulation tool to the vault."""
        with self._lock:
            self._last_sim = {"tool": tool_name, "result": result}
            self._push_count += 1
            self._write()

    def push_queue(self, state: dict[str, Any]) -> None:
        """Push DOM queue state to the vault."""
        with self._lock:
            self._queue = state
            self._push_count += 1
            self._write()

    def push_forecast(self, state: dict[str, Any]) -> None:
        """Push Forecast Index state to the vault (called by forecast_state tool)."""
        with self._lock:
            self._forecast = state
            self._push_count += 1
            self._write()

    def push_all(
        self,
        harmonic: dict[str, Any] | None = None,
        sim_tool: str | None = None,
        sim_result: dict[str, Any] | None = None,
        queue: dict[str, Any] | None = None,
        forecast: dict[str, Any] | None = None,
    ) -> None:
        """Batch update multiple state pockets in one write."""
        with self._lock:
            if harmonic is not None:
                self._harmonic = harmonic
            if sim_tool is not None and sim_result is not None:
                self._last_sim = {"tool": sim_tool, "result": sim_result}
            if queue is not None:
                self._queue = queue
            if forecast is not None:
                self._forecast = forecast
            self._push_count += 1
            self._write()

    # ------------------------------------------------------------------
    # Internal writer
    # ------------------------------------------------------------------

    def _write(self) -> None:
        """Overwrite live-state.md with the current composite snapshot.

        Atomic replace so a crash mid-write cannot leave a truncated note.
        Disk errors are logged and swallowed — a vault hiccup must never
        abort the tool that triggered the push.
        """
        target = self._vault_dir / self.LIVE_STATE_FILE
        tmp = target.with_name(target.name + ".tmp")
        try:
            content = self._render()
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(target)
        except Exception as exc:
            print(f"[vault_hub] write failed: {exc}", file=sys.stderr, flush=True)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _render(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines: list[str] = [
            "# live-state",
            "",
            "#live #state #hub",
            "",
            f"> Machine-generated by `mcp_server/vault_hub.py` — push #{self._push_count}  ",
            f"> Last updated: {ts}",
            "",
            "---",
            "",
            "## Connections",
            "",
            "→ [[HOME]] ← grand central  ",
            "→ [[harmonic-index]] — shard state reflected below  ",
            "→ [[mcp-server]] — tools that write here  ",
            "→ [[sims]] — simulation results reflected below  ",
            "→ [[cognitive/forecasting-engine]] — F=P/A Forecast Index reflected below  ",
            "",
            "---",
            "",
        ]

        # Harmonic index section
        lines += self._render_harmonic()
        lines += ["", "---", ""]

        # Forecast Index section
        lines += self._render_forecast()
        lines += ["", "---", ""]

        # Last simulation section
        lines += self._render_sim()
        lines += ["", "---", ""]

        # DOM queue section
        lines += self._render_queue()
        lines += ["", "---", ""]

        lines.append(
            "*This file is the backwards channel — MCP server state pushed into the vault hub.*"
        )
        return "\n".join(lines) + "\n"

    def _render_harmonic(self) -> list[str]:
        if not self._harmonic:
            return ["## Harmonic index", "", "_No data yet — run `/index` or `/sim <x0>`_"]

        h = self._harmonic
        step = h.get("step", "?")
        alpha = h.get("alpha", 1.96)
        total = h.get("total_activation", 0.0)
        shards = h.get("shards", [])

        lines = [
            "## Harmonic index",
            "",
            f"| Parameter | Value |",
            f"|---|---|",
            f"| Step | {step} |",
            f"| α | {alpha} |",
            f"| Total activation | {round(total, 6)} |",
            "",
            "| Shard | Harmonic | Basin centre | Activation |",
            "|---|---|---|---|",
        ]
        for s in shards:
            bar = _activation_bar(s.get("activation", 0.0), total)
            lines.append(
                f"| {s.get('index', '?')} | {s.get('harmonic', '?')} | {s.get('basin_centre', '?')} "
                f"| {round(float(s.get('activation', 0.0) or 0.0), 6)} {bar} |"
            )
        return lines

    def _render_forecast(self) -> list[str]:
        if not self._forecast:
            return [
                "## Forecast Index (F = P/A)",
                "",
                "_No forecast yet — call `forecast_state` to compute_",
            ]

        f = self._forecast
        fi   = f.get("forecast_index", 0.0)
        fs   = f.get("forecast_smooth", 0.0)
        p    = f.get("passion", 0.0)
        a    = f.get("acquaintance", 0.0)
        entr = f.get("entropy", 0.0)
        stat = f.get("status", "unknown")
        n    = f.get("n_shards", "?")

        # Status → emoji indicator
        indicator = {"underloaded": "🟢", "nominal": "🔵", "elevated": "🟡", "saturated": "🔴"}.get(stat, "⚪")

        lines = [
            "## Forecast Index (F = P/A)",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Status | {indicator} **{stat}** |",
            f"| F (raw) | {round(fi, 4)} |",
            f"| F* (smoothed) | {round(fs, 4)} |",
            f"| P — passion (mean activation) | {round(p, 4)} |",
            f"| A — acquaintance (1 − entropy) | {round(a, 4)} |",
            f"| Entropy | {round(entr, 4)} |",
            f"| Shards sampled | {n} |",
            "",
            "> **F = P/A** — pressure over adaptive capacity.  "
            "High F → vault is saturated.  Low F → headroom available.",
        ]
        return lines

    def _render_sim(self) -> list[str]:
        if not self._last_sim:
            return ["## Last simulation", "", "_No simulation run yet — try `/sim 1.5`_"]

        tool = self._last_sim.get("tool", "unknown")
        result = self._last_sim.get("result", {})

        lines = ["## Last simulation", "", f"**Tool:** `{tool}`", ""]

        if tool == "double_well_sim":
            lines += [
                f"| Field | Value |",
                f"|---|---|",
                f"| x0 | {result.get('x0', '?')} |",
                f"| final_x | {result.get('final_x', '?')} |",
                f"| converged | {result.get('converged', '?')} |",
                f"| steps | {result.get('steps', '?')} |",
                f"| attractor | {result.get('attractor', '?')} |",
                f"| injected shard | {result.get('injected_shard', '—')} |",
            ]
        elif tool == "neg_exp_sim":
            lines += [
                f"| Field | Value |",
                f"|---|---|",
                f"| x0 | {result.get('x0', '?')} |",
                f"| final_x | {result.get('final_x', '?')} |",
                f"| converged | {result.get('converged', '?')} |",
                f"| steps | {result.get('steps', '?')} |",
                f"| error to fixed point | {result.get('error_to_fixed_point', '?')} |",
            ]
        elif tool == "sweep_attractors":
            n = result.get("n_trajectories", "?")
            conv = result.get("converged", "?")
            lines += [
                f"| Field | Value |",
                f"|---|---|",
                f"| trajectories | {n} |",
                f"| converged | {conv} / {n} |",
                f"| α | {result.get('alpha', '?')} |",
            ]
        else:
            for k, v in list(result.items())[:8]:
                lines.append(f"- **{k}**: {v}")

        return lines

    def _render_queue(self) -> list[str]:
        if not self._queue:
            return ["## DOM Request Queue", "", "_No queue data yet_"]

        houses = self._queue.get("houses", [])
        total_calls = self._queue.get("total_calls", 0)

        lines = [
            "## DOM Request Queue",
            "",
            f"Total calls: **{total_calls}**",
            "",
            "| House | Tools | Calls | Active |",
            "|---|---|---|---|",
        ]
        for h in houses:
            active = "▶" if h.get("active") else "·"
            tools_str = ", ".join(f"`{t}`" for t in sorted(h.get("tools", [])))
            lines.append(
                f"| `{h['name']}` | {tools_str} | {h.get('call_count', 0)} | {active} |"
            )
        return lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _activation_bar(value: float, total: float, width: int = 8) -> str:
    """Tiny text bar showing relative activation level."""
    if total < 1e-12 or value < 1e-12:
        return ""
    ratio = min(value / total, 1.0)
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Factory — called at spawn
# ---------------------------------------------------------------------------


def open_vault_hub(project_root: Path) -> VaultHub:
    """
    Instantiate and return a VaultHub pointed at the Obsidian vault.

    Called once at server spawn, alongside spawn_houses().
    The vault IS the project root — packages live inside it.
    """
    hub = VaultHub(vault_dir=project_root)
    return hub
