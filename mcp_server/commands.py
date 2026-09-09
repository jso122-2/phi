"""
Slash-command catalog — stdlib only.

Single source of truth for `/command` → MCP tool (or workflow mode).
Primary surface: `/read <sub>` (inspect) and `/do <sub>` (mutate).
Legacy one-shot slashes still parse as aliases.

Imported by:
  - mcp_server.tools.command   (run_command / list_commands)
  - mcp_server._gate           (command_dispatch pre-hook)
  - .cursor/hooks/command-hook.sh  (beforeSubmitPrompt / shell / MCP)

Do not import numpy, FastMCP, or tool modules from this file.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Final


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandSpec:
    slash: str                          # without leading /
    kind: str                           # "mcp" | "workflow" | "dispatcher"
    description: str
    tool: str | None = None             # MCP tool name
    module: str | None = None           # import path for in-process dispatch
    positionals: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()      # trailing positionals that may be omitted
    types: dict[str, str] = field(default_factory=dict)  # float|int|str|bool
    rest: str | None = None             # leftover tokens joined into this kwarg
    pipe_fields: tuple[str, ...] = ()   # split remainder on |
    bool_flags: tuple[str, ...] = ()    # --cov → coverage=True
    flag_map: dict[str, str] = field(default_factory=dict)  # --top-k → top_k
    context_file: str | None = None
    init_free: bool = False
    defaults: dict[str, Any] = field(default_factory=dict)  # kwargs pre-seeded before parse


@dataclass
class ParsedCommand:
    raw: str
    slash: str
    kind: str
    tool: str | None = None
    module: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)
    context_file: str | None = None
    description: str = ""
    init_free: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "raw": self.raw,
            "command": f"/{self.slash}" if self.slash else "",
            "kind": self.kind,
            "description": self.description,
        }
        if self.error:
            out["error"] = self.error
            return out
        if self.tool:
            out["tool"] = self.tool
            out["kwargs"] = self.kwargs
            out["init_free"] = self.init_free
        elif self.kind == "dispatcher":
            out["subcommands"] = self.kwargs.get("subcommands")
            out["init_free"] = self.init_free
        if self.context_file:
            out["context_file"] = self.context_file
        return out


class CommandParseError(ValueError):
    """Unknown command or malformed arguments."""


# ---------------------------------------------------------------------------
# Catalog builders
# ---------------------------------------------------------------------------


def _mcp(
    slash: str,
    tool: str,
    module: str,
    description: str,
    *,
    positionals: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    types: dict[str, str] | None = None,
    rest: str | None = None,
    pipe_fields: tuple[str, ...] = (),
    bool_flags: tuple[str, ...] = (),
    flag_map: dict[str, str] | None = None,
    init_free: bool = False,
    defaults: dict[str, Any] | None = None,
) -> CommandSpec:
    return CommandSpec(
        slash=slash,
        kind="mcp",
        tool=tool,
        module=module,
        description=description,
        positionals=positionals,
        optional=optional,
        types=types or {},
        rest=rest,
        pipe_fields=pipe_fields,
        bool_flags=bool_flags,
        flag_map=flag_map or {},
        init_free=init_free,
        defaults=defaults or {},
    )


def _wf(slash: str, context_file: str, description: str) -> CommandSpec:
    return CommandSpec(
        slash=slash,
        kind="workflow",
        description=description,
        context_file=context_file,
        init_free=True,
    )


def _disp(slash: str, description: str) -> CommandSpec:
    return CommandSpec(
        slash=slash,
        kind="dispatcher",
        description=description,
        init_free=True,
    )


_SIMS = "mcp_server.tools.sims"
_HARM = "mcp_server.tools.harmonic"
_SEARCH = "mcp_server.tools.search"
_GRAPH = "mcp_server.tools.graph"
_SYS = "mcp_server.tools.system"
_CAIRRN = "mcp_server.tools.cairrn"
_TEMP = "mcp_server.tools.temporal"
_PHI = "mcp_server.tools.phi_dispatch"
_CLIP = "mcp_server.tools.phi_clip"
_SHUF = "mcp_server.tools.prefeed_shuffle"
_BUS = "mcp_server.tools.bus"
_FORE = "mcp_server.tools.forecast"
_MOD = "mcp_server.tools.modular"
_RATE = "mcp_server.tools.rate"
_NTN = "mcp_server.tools.notion_reservoir"
_CTX = "mcp_server.tools.context_modes"


SPECS: tuple[CommandSpec, ...] = (
    # -- simulation --------------------------------------------------------
    _mcp("sim", "double_well_sim", _SIMS, "Double-well gradient descent from x0.",
         positionals=("x0",), types={"x0": "float", "lr": "float", "alpha": "float"},
         bool_flags=("inject", "inject_into_index")),
    _mcp("neg-exp", "neg_exp_sim", _SIMS, "Iterate f(x)=−eˣ from x0.",
         positionals=("x0",), types={"x0": "float"}),
    _mcp("sweep", "sweep_attractors", _SIMS, "Sweep double-well initial conditions.",
         optional=("x0_min", "x0_max", "n_points"),
         types={"x0_min": "float", "x0_max": "float", "n_points": "int", "alpha": "float"}),
    _mcp("langevin", "langevin_sim", _SIMS, "Overdamped Langevin on the double well.",
         positionals=("x0",),
         types={"x0": "float", "noise_scale": "float", "steps": "int", "lr": "float", "alpha": "float", "seed": "int"}),
    _mcp("mfpt", "mfpt_estimate", _SIMS, "Mean first passage time vs Kramers.",
         optional=("noise_scale",),
         types={"noise_scale": "float", "n_trials": "int", "seed": "int"}),
    _mcp("ana-chi", "ana_chi_sim", _SIMS, "Ana-Chi 5-basin flow.",
         optional=("chi_0",), types={"chi_0": "float", "lr": "float", "max_iter": "int"}),
    _mcp("ana-chi-state", "ana_chi_state", _SIMS, "Ana-Chi basin snapshot.",
         optional=("chi",), types={"chi": "float"}),

    # -- harmonic index ----------------------------------------------------
    _mcp("index", "harmonic_index_state", _HARM, "Print 8-shard harmonic index."),
    _mcp("propagate", "harmonic_propagate", _HARM, "Advance harmonic propagation.",
         optional=("steps",), types={"steps": "int"}),
    _mcp("inject", "harmonic_inject", _HARM, "Inject activation into a shard.",
         positionals=("shard_index", "value"), types={"shard_index": "int", "value": "float"}),
    _mcp("reset", "harmonic_reset", _HARM, "Re-seed the ring to a warm HOME floor."),
    _mcp("hub-state", "hub_state", _HARM, "Harmonic index by station hub."),
    _mcp("hub-inject", "hub_inject", _HARM, "Inject via station-hub name.",
         positionals=("hub_name", "value"), types={"value": "float"}),
    _mcp("set-goal", "harmonic_set_goal", _HARM, "Set goal-directed propagation target.",
         positionals=("target_shard",), types={"target_shard": "int", "value": "float", "goal_strength": "float"}),
    _mcp("clear-goal", "harmonic_clear_goal", _HARM, "Clear harmonic goal vector."),

    # -- RAG ---------------------------------------------------------------
    _mcp("psspps", "psspps_query", _SEARCH, "PSSPPS vault RAG query.",
         rest="query", types={"top_k": "int", "perspective_alpha": "float", "wait_s": "float"},
         flag_map={"alpha": "perspective_alpha", "top-k": "top_k", "wait": "wait_s"}),
    _mcp("find", "agent_context", _CTX,
         "Hybrid search — Notion pages first, vault retrieval fallback.",
         defaults={"mode": "find"}, init_free=True),

    # -- graph -------------------------------------------------------------
    _mcp("graph-commit", "graph_commit", _GRAPH,
         "Write this session as a vault node.",
         pipe_fields=("prompt", "thinking", "outcome"), types={"wait_s": "float"}),
    _mcp("graph-clean", "graph_clean", _GRAPH, "Scan orphans + dead wikilinks.", init_free=True),
    _mcp("graph-nest", "graph_nest", _GRAPH, "Suggest hub tags for untagged nodes.", init_free=True),
    _mcp("graph-link", "graph_link", _GRAPH, "Auto-link semantically related nodes.",
         types={"threshold": "float", "wait_s": "float"}),
    _mcp("graph-status", "graph_status", _GRAPH, "Vault graph health snapshot.", init_free=True),
    _mcp("graph-traverse", "graph_traverse", _GRAPH, "Walk the vault from a seed.",
         rest="seed", types={"max_hops": "int", "top_k": "int", "sim_floor": "float", "wait_s": "float", "context_budget": "int"},
         flag_map={"top-k": "top_k", "hops": "max_hops"}),
    _mcp("graph-topo-hubs", "graph_topo_hubs", _GRAPH, "Elect hubs from wikilink components.",
         types={"min_component_size": "int"},
         bool_flags=("write_tags", "write-tags", "apply_cairrn", "apply-cairrn"),
         flag_map={"prefix": "prefix_filter", "min-size": "min_component_size"}),
    # /cairrn-topo — shorthand for /graph-topo-hubs --apply-cairrn
    _mcp("cairrn-topo", "graph_topo_hubs", _GRAPH,
         "Run topology hub election and pipe cairrn_snapshot through CAIRRNBridge overlay.",
         types={"min_component_size": "int"},
         bool_flags=("write_tags", "write-tags", "apply_cairrn", "apply-cairrn"),
         flag_map={"prefix": "prefix_filter", "min-size": "min_component_size"},
         defaults={"apply_cairrn": True}),
    _mcp("graph-ingest", "graph_ingest", _GRAPH, "Ingest a directory into vault nodes.",
         positionals=("source_dir",), bool_flags=("dry_run", "dry-run"),
         types={"max_files": "int", "wait_s": "float"},
         flag_map={"max-files": "max_files"}),
    _mcp("graph-ingest-source", "graph_ingest_source", _GRAPH, "AST-extract Python modules into source/ nodes.",
         bool_flags=("dry_run", "dry-run"), rest="packages"),
    _mcp("graph-sync-manifest", "graph_sync_manifest", _GRAPH, "Pulse hubs from an ingest manifest.",
         optional=("manifest_path",)),
    _mcp("graph-track", "graph_track_state", _GRAPH, "Usage ledger + git-hot notes.", init_free=True),
    _mcp("graph-track-sync", "graph_track_sync", _GRAPH, "Apply heat to .gitignore and the git index."),
    _mcp("graph-annotate", "graph_annotate", _GRAPH, "Write an agent commentary node.",
         pipe_fields=("target_stem", "comment"), types={"confidence": "float"}),
    _mcp("vault-hub", "vault_hub_state", _GRAPH, "Live vault-hub snapshot."),
    _mcp("vault-store", "vault_store_stats", _GRAPH,
         "SQL vault store snapshot — nodes by layer, edges, usage events.", init_free=True),
    _mcp("vault-project", "vault_project", _GRAPH,
         "Re-materialise a session .md from its SQL row.",
         positionals=("node_id",), bool_flags=("force",)),
    _mcp("vault-migrate", "vault_migrate", _GRAPH,
         "Scan vault .md files and upsert into SQL store.",
         optional=("batch_size",), types={"batch_size": "int"}),
    _mcp("context-state", "system_status", _SYS,
         "Session-open PSSPPS handshake (via system_status).", init_free=True),

    # -- system ------------------------------------------------------------
    _mcp("status", "system_status", _SYS, "Full health report — env + index.", init_free=True),
    _mcp("health", "init_check", _SYS, "Environment-only init / gate check.", init_free=True),
    _mcp("test", "run_tests", _SYS, "Run the pytest suite.",
         optional=("mode",), bool_flags=("cov", "coverage"),
         flag_map={"cov": "coverage"}),
    _mcp("watchdog", "watchdog_state", _SYS, "Race-watchdog stall + contention."),
    _mcp("hooks", "list_hooks", _SYS, "Inspect the append-only pre-hook chain.", init_free=True),
    _mcp("queue", "dom_queue_state", _SYS, "DOM house queue snapshot.", init_free=True),
    _mcp("commands", "list_commands", "mcp_server.tools.command",
         "List every slash command and its MCP tool.", init_free=True),

    # -- CAIRRN (arity of /cairrn is special-cased in parse_command) -------
    _mcp("cairrn-state", "cairrn_hub_state", _CAIRRN, "Static CAIRRN hub geometry."),
    _mcp("cairrn", "hub_state", _HARM,
         "Hub geometry; /cairrn <hub> <metric> runs the CAIRRN pipeline."),
    _mcp("cairrn-run", "cairrn_hub_run", _CAIRRN, "Run CAIRRN pipeline for one hub.",
         positionals=("hub_name", "metric"), types={"metric": "float"}),
    _mcp("cairrn-batch", "cairrn_batch_run", _CAIRRN, "Run CAIRRN across all hubs.",
         optional=("metric",), types={"metric": "float"}),
    _mcp("cairrn-css", "cairrn_css_state", _CAIRRN, "CSS bitmask / middle-shard state."),
    _mcp("cairrn-m3", "cairrn_m3_gate", _CAIRRN, "M3 quality gate."),
    _mcp("cairrn-k", "cairrn_neuro_k", _CAIRRN, "Neuro-activation K formula chain.",
         positionals=("tracer_consensus_value",),
         types={"tracer_consensus_value": "float", "SHI": "float", "jules": "float"},
         bool_flags=("inject",)),

    # -- temporal ----------------------------------------------------------
    _mcp("temporal-state", "temporal_state", _TEMP, "Temporal sharding index state."),
    _mcp("temporal-vector", "temporal_vector", _TEMP, "Hub × window activation matrix."),
    _mcp("temporal-coherence", "temporal_coherence", _TEMP, "Ana-Chi coherence of the temporal index."),
    _mcp("temporal-record", "temporal_record", _TEMP, "Record hub activation at t=0.",
         positionals=("hub_name", "value"), types={"value": "float"}),
    _mcp("temporal-advance", "temporal_advance", _TEMP, "Advance the temporal clock.",
         optional=("steps",), types={"steps": "int"}),
    _mcp("temporal-reset", "temporal_reset", _TEMP, "Zero temporal activations."),

    # -- phi / shuffle / clip ----------------------------------------------
    _mcp("phi-enqueue", "phi_enqueue", _PHI, "Enqueue a CAIRRN-gated phi action.",
         positionals=("kind",), rest="query",
         types={"shard_index": "int", "value": "float", "metric": "float",
                "top_k": "int", "alpha": "float", "steps": "int", "priority": "int"},
         flag_map={"hub": "hub_name", "shard": "shard_index", "top-k": "top_k"}),
    _mcp("phi-step", "phi_step", _PHI, "One CAIRRN dispatcher clock tick."),
    _mcp("phi-queue", "phi_queue", _PHI, "Inspect phi dispatcher queue + gate."),
    _mcp("phi-flush", "phi_flush", _PHI, "Force-dispatch all queued phi actions."),
    _mcp("clip", "gemini_clip", _CLIP, "Clip top-K library tracks for a query.",
         rest="query", types={"top_k": "int", "blend": "float"},
         flag_map={"top-k": "top_k"}),
    _mcp("shuffle-seed", "shuffle_seed", _SHUF, "Bootstrap the CAIRRN prefeed shuffle."),
    _mcp("shuffle-step", "shuffle_step", _SHUF, "One shuffle scheduler tick."),
    _mcp("shuffle-next", "shuffle_next", _SHUF, "Advance shuffle cursor.",
         optional=("peek_ahead",), types={"peek_ahead": "int"},
         flag_map={"peek": "peek_ahead"}),
    _mcp("shuffle-state", "shuffle_state", _SHUF, "Inspect shuffle + gate state."),

    # -- bus / forecast / audit --------------------------------------------
    _mcp("bus-submit", "bus_submit", _BUS, "Enqueue a scheduler bus job.",
         positionals=("task",), rest="payload_json"),
    _mcp("bus-poll", "bus_poll", _BUS, "Poll a bus job by id.",
         positionals=("job_id",), init_free=True),
    _mcp("bus-wait", "bus_wait", _BUS, "Wait for a bus job.",
         positionals=("job_id",), types={"timeout_s": "float"},
         flag_map={"timeout": "timeout_s"}),
    _mcp("bus-status", "bus_status", _BUS, "Singleton scheduler snapshot.", init_free=True),
    _mcp("bus-restart", "bus_restart", _BUS, "Restart the bus scheduler."),
    _mcp("forecast", "forecast_state", _FORE, "Forecast pocket snapshot.", init_free=True),
    _mcp("code-audit", "code_audit", _MOD, "Read-only code structure audit.",
         positionals=("target",), optional=("mode",)),
    _mcp("10", "rate_ten", _RATE, "Rate a project or module out of 10.",
         optional=("target",)),
    _mcp("coherence-state", "coherence_state", _SYS,
         "Session harmonic trajectory + BMAD pressure signals.", init_free=True,
         optional=("tail",), types={"tail": "int"}),

    # -- umbrellas + workflow modes ----------------------------------------
    _disp("do", "Mutate — sim, inject, commit, enqueue, …"),
    _mcp("talk",    "agent_context", _CTX, "Strategic discussion — align before building.",
         defaults={"mode": "talk"},    init_free=True),
    _mcp("explain", "agent_context", _CTX, "Plain-language explanation.",
         defaults={"mode": "explain"}, init_free=True),
    _mcp("dev",     "agent_context", _CTX, "Build mode — write, run, iterate.",
         defaults={"mode": "dev"},     init_free=True),
    _mcp("modular", "agent_context", _CTX, "Package raw output cleanly.",
         defaults={"mode": "modular"}, init_free=True),
    _mcp("wire",    "agent_context", _CTX, "Connect imports, interfaces, pipeline.",
         defaults={"mode": "wire"},    init_free=True),
    _mcp("edit",    "agent_context", _CTX, "Surgical inline fixes.",
         defaults={"mode": "edit"},    init_free=True),
    _mcp("clean",   "agent_context", _CTX, "Fix repo file tree.",
         defaults={"mode": "clean"},   init_free=True),
    _mcp("audit",   "agent_context", _CTX, "Three-layer health audit.",
         defaults={"mode": "audit"},   init_free=True),
    _mcp("read",    "agent_context", _CTX,
         "Inspect — bare loads vault context; /read <sub> dispatches.",
         defaults={"mode": "read"},    init_free=True),
)

CATALOG: Final[dict[str, CommandSpec]] = {s.slash: s for s in SPECS}

# Primary slash alias for each MCP tool (first spec that names it wins).
TOOL_TO_SLASH: Final[dict[str, str]] = {}
for _spec in SPECS:
    if _spec.tool and _spec.tool not in TOOL_TO_SLASH:
        TOOL_TO_SLASH[_spec.tool] = _spec.slash

# /cairrn with hub+metric is special-cased in parse_command → cairrn_hub_run.

# Inspect umbrella: /read <sub> → catalog slash. Values must exist in CATALOG.
READ_SUBS: Final[dict[str, str]] = {
    "status": "status",
    "health": "health",
    "index": "index",
    "hub": "hub-state",
    "ana-chi": "ana-chi-state",
    "graph": "graph-status",
    "clean": "graph-clean",
    "nest": "graph-nest",
    "track": "graph-track",
    "traverse": "graph-traverse",
    "vault": "vault-hub",
    "watchdog": "watchdog",
    "hooks": "hooks",
    "queue": "queue",
    "commands": "commands",
    "cairrn": "cairrn-state",
    "css": "cairrn-css",
    "m3": "cairrn-m3",
    "temporal": "temporal-state",
    "vector": "temporal-vector",
    "temporal-coherence": "temporal-coherence",
    "phi": "phi-queue",
    "shuffle": "shuffle-state",
    "bus": "bus-status",
    "poll": "bus-poll",
    "forecast": "forecast",
    "coherence": "coherence-state",
    "psspps": "psspps",
    "find": "find",
    "audit": "code-audit",
    "context": "context-state",
    "vault-store": "vault-store",
}

# Mutate umbrella: /do <sub> → catalog slash. Values must exist in CATALOG.
DO_SUBS: Final[dict[str, str]] = {
    "sim": "sim",
    "neg-exp": "neg-exp",
    "sweep": "sweep",
    "langevin": "langevin",
    "mfpt": "mfpt",
    "ana-chi": "ana-chi",
    "propagate": "propagate",
    "inject": "inject",
    "reset": "reset",
    "hub-inject": "hub-inject",
    "set-goal": "set-goal",
    "clear-goal": "clear-goal",
    "commit": "graph-commit",
    "link": "graph-link",
    "topo": "graph-topo-hubs",
    "cairrn-topo": "cairrn-topo",
    "ingest": "graph-ingest",
    "ingest-source": "graph-ingest-source",
    "sync": "graph-sync-manifest",
    "track-sync": "graph-track-sync",
    "annotate": "graph-annotate",
    "test": "test",
    "cairrn": "cairrn-run",
    "batch": "cairrn-batch",
    "k": "cairrn-k",
    "record": "temporal-record",
    "advance": "temporal-advance",
    "temporal-reset": "temporal-reset",
    "enqueue": "phi-enqueue",
    "step": "phi-step",
    "flush": "phi-flush",
    "clip": "clip",
    "seed": "shuffle-seed",
    "shuffle-step": "shuffle-step",
    "next": "shuffle-next",
    "submit": "bus-submit",
    "wait": "bus-wait",
    "restart": "bus-restart",
    "10": "10",
    "vault-project": "vault-project",
    "vault-migrate": "vault-migrate",
}

_HELP_TOKS: Final[frozenset[str]] = frozenset({"help", "--help", "--list", "subs", "subcommands"})


def _resolve_sub(group: str, sub: str) -> str | None:
    """Map an umbrella subcommand (or a legacy slash) to a CATALOG key."""
    mapping = READ_SUBS if group == "read" else DO_SUBS
    if sub in mapping:
        return mapping[sub]
    if sub in mapping.values():
        return sub
    return None


def _args_for(spec: CommandSpec) -> list[str]:
    args = list(spec.positionals)
    if spec.optional:
        args.extend(f"[{n}]" for n in spec.optional)
    if spec.rest:
        args.append(f"<{spec.rest}…>")
    if spec.pipe_fields:
        args = [" | ".join(f"<{n}>" for n in spec.pipe_fields)]
    return args


def _spec_row(spec: CommandSpec) -> dict[str, Any]:
    row: dict[str, Any] = {
        "command": f"/{spec.slash}",
        "kind": spec.kind,
        "description": spec.description,
        "init_free": spec.init_free,
    }
    if spec.tool:
        row["tool"] = spec.tool
        row["args"] = _args_for(spec)
    if spec.context_file:
        row["context_file"] = spec.context_file
    return row


def _subs_listing(group: str) -> list[dict[str, Any]]:
    mapping = READ_SUBS if group == "read" else DO_SUBS
    rows: list[dict[str, Any]] = []
    for sub, slash in mapping.items():
        spec = CATALOG[slash]
        row = _spec_row(spec)
        row["sub"] = sub
        row["command"] = f"/{group} {sub}"
        row["alias"] = f"/{slash}"
        rows.append(row)
    return rows


def _dispatcher_parsed(group: str, raw: str) -> ParsedCommand:
    spec = CATALOG[group]
    return ParsedCommand(
        raw=raw,
        slash=group,
        kind="dispatcher",
        kwargs={"subcommands": _subs_listing(group)},
        context_file=spec.context_file,
        description=spec.description,
        init_free=True,
    )


def _parse_read(raw: str, rest: str) -> ParsedCommand:
    sub, remainder = _first_rest(rest)
    if sub and sub.lower() in _HELP_TOKS:
        return _dispatcher_parsed("read", raw)
    if sub:
        slash = _resolve_sub("read", sub.lower())
        if slash is not None:
            return _from_spec(raw, CATALOG[slash], remainder)
    spec = CATALOG["read"]
    kwargs: dict[str, Any] = {"topic": rest.strip()} if rest.strip() else {}
    return ParsedCommand(
        raw=raw,
        slash="read",
        kind="workflow",
        context_file=spec.context_file,
        description=spec.description,
        init_free=True,
        kwargs=kwargs,
    )


def _parse_do(raw: str, rest: str) -> ParsedCommand:
    sub, remainder = _first_rest(rest)
    if not sub or sub.lower() in _HELP_TOKS:
        return _dispatcher_parsed("do", raw)
    slash = _resolve_sub("do", sub.lower())
    if slash is None:
        close = [s for s in DO_SUBS if s.startswith(sub.lower()[:3])]
        hint = f" Did you mean: {', '.join('/do ' + c for c in close[:5])}?" if close else ""
        raise CommandParseError(
            f"unknown /do subcommand {sub!r}.{hint} Try /do help."
        )
    return _from_spec(raw, CATALOG[slash], remainder)


def _first_rest(rest: str) -> tuple[str, str]:
    text = rest.strip()
    if not text:
        return "", ""
    first, _, tail = text.partition(" ")
    return first, tail.strip()


def alias_map() -> dict[str, str]:
    """Legacy `/{slash}` → primary `/{read|do} <sub>`."""
    out: dict[str, str] = {}
    for sub, slash in READ_SUBS.items():
        out[f"/{slash}"] = f"/read {sub}"
    for sub, slash in DO_SUBS.items():
        out[f"/{slash}"] = f"/do {sub}"
    out["/cairrn"] = "/do cairrn"
    return out


_missing_umbrella = [
    v for v in (*READ_SUBS.values(), *DO_SUBS.values()) if v not in CATALOG
]
if _missing_umbrella:
    raise RuntimeError(f"umbrella targets missing from CATALOG: {_missing_umbrella}")

# Dual-arity /cairrn stays a legacy slash (bare → hub_state, args → cairrn_hub_run).
# agent_context modes (talk/dev/explain/…) are standalone entry-points, not sub-commands.
_UMBRELLA_EXEMPT: Final[frozenset[str]] = frozenset({"cairrn", "read", "do"})
_mcp_orphans = [
    s.slash
    for s in SPECS
    if s.kind == "mcp"
    and s.slash not in READ_SUBS.values()
    and s.slash not in DO_SUBS.values()
    and s.slash not in _UMBRELLA_EXEMPT
    and s.tool != "agent_context"   # standalone mode entry-points
]
if _mcp_orphans:
    raise RuntimeError(f"MCP slashes missing from /read or /do: {_mcp_orphans}")

# ---------------------------------------------------------------------------
# Tokenise / coerce
# ---------------------------------------------------------------------------


_CMD_RE = re.compile(
    r"(?:^|\s)/(?P<name>[a-z0-9][a-z0-9-]*)(?P<rest>[^\n]*)",
    re.IGNORECASE,
)


def _coerce(value: str, kind: str) -> Any:
    if kind == "float":
        return float(value)
    if kind == "int":
        return int(value, 10) if isinstance(value, str) and value.lower().startswith("0x") else int(value)
    if kind == "bool":
        return value.lower() not in {"0", "false", "no", "off"}
    return value


def _flag_key(raw: str, spec: CommandSpec) -> str:
    key = raw.lstrip("-").replace("-", "_")
    mapped = spec.flag_map.get(raw.lstrip("-")) or spec.flag_map.get(key)
    return mapped or key


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in text.strip():
        if quote:
            if ch == quote:
                quote = ""
            else:
                buf.append(ch)
            continue
        if ch in {'"', "'"}:
            quote = ch
            continue
        if ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _split_flags(
    tokens: list[str], spec: CommandSpec,
) -> tuple[list[str], dict[str, str], set[str]]:
    positionals: list[str] = []
    flags: dict[str, str] = {}
    bools: set[str] = set()
    bool_names = {b.replace("-", "_") for b in spec.bool_flags}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            body = tok[2:]
            if "=" in body:
                k, v = body.split("=", 1)
                flags[_flag_key(k, spec)] = v
            else:
                key = _flag_key(body, spec)
                nxt = tokens[i + 1] if i + 1 < len(tokens) else None
                if key.replace("-", "_") in bool_names or body.replace("-", "_") in bool_names:
                    bools.add(key.replace("-", "_"))
                elif nxt is not None and not nxt.startswith("-"):
                    flags[key] = nxt
                    i += 1
                else:
                    bools.add(key.replace("-", "_"))
        else:
            positionals.append(tok)
        i += 1
    return positionals, flags, bools


def _apply_types(kwargs: dict[str, Any], spec: CommandSpec) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in kwargs.items():
        if v is None or v == "":
            continue
        kind = spec.types.get(k)
        if kind and isinstance(v, str):
            try:
                out[k] = _coerce(v, kind)
            except (TypeError, ValueError) as exc:
                raise CommandParseError(
                    f"/{spec.slash}: argument {k}={v!r} is not a valid {kind}"
                ) from exc
        else:
            out[k] = v
    return out


def _fill_positionals(
    spec: CommandSpec, positionals: list[str],
) -> dict[str, Any]:
    names = spec.positionals + spec.optional
    required = len(spec.positionals)
    kwargs: dict[str, Any] = {}
    if spec.rest:
        # Required named positionals first, remainder joined into rest.
        head, tail = names[:required], positionals
        if len(tail) < required:
            raise CommandParseError(
                f"/{spec.slash} requires {', '.join(spec.positionals)}"
            )
        for name, val in zip(head, tail):
            kwargs[name] = val
        rest_tokens = tail[required:]
        if rest_tokens:
            kwargs[spec.rest] = " ".join(rest_tokens)
        elif required == 0 and spec.rest not in kwargs:
            # rest-only command with no tokens
            pass
        return kwargs

    if len(positionals) < required:
        need = ", ".join(spec.positionals)
        raise CommandParseError(f"/{spec.slash} requires positional args: {need}")
    extra = len(positionals) - len(names)
    if extra > 0 and not spec.rest:
        positionals = positionals[:len(names)]
    for name, val in zip(names, positionals):
        kwargs[name] = val
    return kwargs


def _from_spec(raw: str, spec: CommandSpec, remainder: str) -> ParsedCommand:
    if spec.pipe_fields:
        parts = [p.strip() for p in remainder.split("|")]
        if remainder.strip() and len(parts) < len(spec.pipe_fields):
            raise CommandParseError(
                f"/{spec.slash} requires {' | '.join('<' + f + '>' for f in spec.pipe_fields)}"
            )
        kwargs: dict[str, Any] = dict(spec.defaults)  # seed from spec defaults
        kwargs.update({
            name: parts[i] for i, name in enumerate(spec.pipe_fields)
            if i < len(parts) and parts[i]
        })
        flag_tokens = [t for t in _tokenize(remainder) if t.startswith("--")]
        _, flags, bools = _split_flags(flag_tokens, spec)
        kwargs.update(flags)
        for b in bools:
            kwargs[b if b in spec.types or b in spec.bool_flags else b] = True
        # bool flag aliases: --cov → coverage
        if "cov" in kwargs and "coverage" not in kwargs:
            kwargs["coverage"] = True
            kwargs.pop("cov", None)
        return ParsedCommand(
            raw=raw, slash=spec.slash, kind=spec.kind, tool=spec.tool,
            module=spec.module, kwargs=_apply_types(kwargs, spec),
            description=spec.description, init_free=spec.init_free,
        )

    tokens = _tokenize(remainder)
    positionals, flags, bools = _split_flags(tokens, spec)
    kwargs = dict(spec.defaults)  # seed from spec defaults
    kwargs.update(_fill_positionals(spec, positionals))
    kwargs.update(flags)
    for b in bools:
        target = "coverage" if b in {"cov", "coverage"} else b
        if b in {"inject", "inject_into_index"}:
            target = "inject_into_index"
        if b in {"dry_run", "dry-run"}:
            target = "dry_run"
        if b in {"write_tags", "write-tags"}:
            target = "write_tags"
        if b in {"apply_cairrn", "apply-cairrn"}:
            target = "apply_cairrn"
        kwargs[target] = True
    if spec.rest and spec.slash in {"psspps", "find", "clip", "graph-traverse"}:
        if not str(kwargs.get(spec.rest, "")).strip():
            raise CommandParseError(f"/{spec.slash} requires a {spec.rest}")
    return ParsedCommand(
        raw=raw, slash=spec.slash, kind=spec.kind, tool=spec.tool,
        module=spec.module, kwargs=_apply_types(kwargs, spec),
        context_file=spec.context_file, description=spec.description,
        init_free=spec.init_free,
    )


# ---------------------------------------------------------------------------
# Public parse API
# ---------------------------------------------------------------------------


def parse_command(raw: str) -> ParsedCommand:
    """
    Parse a slash command string into a ParsedCommand.

    Accepts `/sim 1.5`, `sim 1.5`, or a longer prompt containing a known
    `/command`. Raises CommandParseError on unknown / malformed input.
    """
    text = (raw or "").strip()
    if not text:
        raise CommandParseError("empty command")

    extracted = extract_command(text)
    if extracted is None:
        tokens = _tokenize(text)
        if not tokens:
            raise CommandParseError("empty command")
        first_raw = tokens[0]
        first = first_raw.lstrip("/").lower()
        if first_raw.startswith("/") or text.lstrip().startswith("/"):
            if first not in CATALOG:
                close = [s for s in CATALOG if s.startswith(first[:3])]
                hint = f" Did you mean: {', '.join('/' + c for c in close[:5])}?" if close else ""
                raise CommandParseError(f"unknown command /{first}.{hint}")
            extracted = text if text.startswith("/") else "/" + text
        elif first in CATALOG:
            extracted = "/" + text
        else:
            raise CommandParseError(f"no known slash command in {text!r}")

    body = extracted.lstrip()
    if not body.startswith("/"):
        body = "/" + body
    name_rest = body[1:]
    name, _, rest = name_rest.partition(" ")
    name = name.lower().strip()
    rest = rest.strip()

    # /read <sub> inspects; bare /read loads vault context.
    if name == "read":
        return _parse_read(extracted if extracted.startswith("/") else "/" + extracted, rest)
    # /do <sub> mutates; bare /do lists subcommands.
    if name == "do":
        return _parse_do(extracted if extracted.startswith("/") else "/" + extracted, rest)

    # /cairrn with hub+metric → cairrn_hub_run; bare /cairrn → hub_state.
    if name == "cairrn":
        tokens = _tokenize(rest)
        positionals = [t for t in tokens if not t.startswith("-")]
        if len(positionals) >= 2:
            spec = CATALOG["cairrn-run"]
            return _from_spec(extracted, spec, rest)
        if positionals:
            raise CommandParseError(
                "/cairrn needs `<hub> <metric>` to run the pipeline "
                "(or no args for hub_state)"
            )
        spec = CATALOG["cairrn"]
        return _from_spec(extracted, spec, rest)

    spec = CATALOG.get(name)
    if spec is None:
        close = [s for s in CATALOG if s.startswith(name[:3])]
        hint = f" Did you mean: {', '.join('/' + c for c in close[:5])}?" if close else ""
        raise CommandParseError(f"unknown command /{name}.{hint}")

    return _from_spec(extracted if extracted.startswith("/") else "/" + extracted, spec, rest)


def extract_command(text: str) -> str | None:
    """Return the first known `/command …` substring in text, or None."""
    for match in _CMD_RE.finditer(text):
        name = match.group("name").lower()
        if name in CATALOG:
            rest = match.group("rest") or ""
            return f"/{name}{rest}".strip()
    return None


def list_catalog(*, aliases: bool = False) -> list[dict[str, Any]]:
    """Serialisable catalog for list_commands / agents.

    Primary view is `/read` + `/do` (nested subcommands) plus workflow
    modes. Pass aliases=True for the flat legacy slash list.
    """
    if aliases:
        return [_spec_row(spec) for spec in SPECS]

    read_row: dict[str, Any] = {
        "command": "/read",
        "kind": "dispatcher",
        "description": (
            "Inspect. Bare /read loads vault context; "
            "/read <sub> dispatches a read-only tool."
        ),
        "init_free": True,
        "context_file": ".ai_agent_context/read.md",
        "subcommands": _subs_listing("read"),
    }
    do_row: dict[str, Any] = {
        "command": "/do",
        "kind": "dispatcher",
        "description": "Mutate — sim, inject, commit, enqueue, …",
        "init_free": True,
        "subcommands": _subs_listing("do"),
    }
    rows = [read_row, do_row]
    for spec in SPECS:
        # Show agent_context modes (formerly "workflow") in the primary view.
        if spec.tool == "agent_context" and spec.slash not in ("read",):
            rows.append(_spec_row(spec))
    return rows


def slash_for_tool(tool_name: str) -> str | None:
    name = TOOL_TO_SLASH.get(tool_name)
    return f"/{name}" if name else None


# ---------------------------------------------------------------------------
# Cursor hook handlers (JSON in / JSON out)
# ---------------------------------------------------------------------------


_WORKFLOW_ROOT_HINT = (
    "Read that file immediately and follow its behaviour contract "
    "for the rest of this session. Do not skip it."
)


def handle_submit_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    """beforeSubmitPrompt — inject MCP dispatch instructions."""
    text = _prompt_text(payload)
    extracted = extract_command(text)
    if extracted is None:
        return {"continue": True}
    try:
        parsed = parse_command(extracted)
    except CommandParseError as exc:
        known = "/read help  /do help  /read index  /do sim 1.5"
        return {
            "continue": True,
            "additional_context": (
                f"SLASH COMMAND ERROR: {exc}\n"
                f"Call MCP list_commands (or run_command) to see the catalog.\n"
                f"Examples: {known} …"
            ),
        }
    return {
        "continue": True,
        "additional_context": _dispatch_context(parsed),
    }


def handle_shell(payload: dict[str, Any]) -> dict[str, Any]:
    """beforeShellExecution — block slash commands leaked to the shell."""
    command = str(payload.get("command") or payload.get("cmd") or "").strip()
    if not command.startswith("/"):
        return {"permission": "allow"}
    first = command.split()[0].lstrip("/").lower()
    if first not in CATALOG:
        return {"permission": "allow"}
    try:
        parsed = parse_command(command)
        target = parsed.tool or parsed.context_file or parsed.slash
    except CommandParseError:
        target = first
    return {
        "permission": "deny",
        "user_message": (
            f"/{first} is an MCP command, not a shell command."
        ),
        "agent_message": (
            f"[hook:command] Do not Shell `/{first}`. "
            f"Call MCP run_command with command={command!r} "
            f"(resolves to {target})."
        ),
    }


def handle_mcp_pre(payload: dict[str, Any]) -> dict[str, Any]:
    """beforeMCPExecution — allow; annotate slash alias + gate reminder."""
    server = str(
        payload.get("server")
        or payload.get("server_name")
        or payload.get("serverName")
        or ""
    )
    tool = str(
        payload.get("tool")
        or payload.get("tool_name")
        or payload.get("toolName")
        or ""
    )
    if server and server not in {"spotify-rip", "user-spotify-rip"}:
        return {"permission": "allow"}
    alias = slash_for_tool(tool)
    if tool in {
        "init_check", "system_status", "list_hooks", "register_hook",
        "dom_queue_state", "graph_status", "graph_clean", "graph_nest",
        "graph_track_state", "forecast_state", "bus_poll", "bus_status",
        "run_command", "list_commands",
    }:
        msg = f"[hook:command] {alias} → {tool}" if alias else None
        if msg:
            return {"permission": "allow", "agent_message": msg}
        return {"permission": "allow"}
    parts = [f"[hook:command] {alias} → {tool}" if alias else f"[hook:mcp-pre-call] {tool}"]
    parts.append("gate must be open; call init_check() if you receive session_not_initialized")
    return {
        "permission": "allow",
        "agent_message": " — ".join(parts),
    }


def _prompt_text(payload: dict[str, Any]) -> str:
    for key in ("prompt", "content", "text", "message", "command"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # Nested Cursor shapes
    inner = payload.get("input") or payload.get("arguments") or {}
    if isinstance(inner, dict):
        for key in ("prompt", "content", "text"):
            val = inner.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return ""


def _dispatch_context(parsed: ParsedCommand) -> str:
    # agent_context modes: dispatch instruction (kind=="mcp", tool=="agent_context")
    if parsed.tool == "agent_context":
        mode = parsed.kwargs.get("mode", parsed.slash)
        return (
            f"SLASH COMMAND DISPATCH — call this MCP tool immediately. "
            f"Do not use Shell. Do not ask the user to run it.\n"
            f"Command: {parsed.raw}\n"
            f"Preferred: run_command(command={parsed.raw!r})\n"
            f"Direct: agent_context(mode={mode!r})\n"
            f"{parsed.description}\n"
            f"The tool returns the full contract. "
            f"Follow it for the remainder of the session."
        )
    if parsed.kind == "workflow":
        # Legacy fallback (should not be reached after migration to _mcp).
        topic = parsed.kwargs.get("topic")
        extra = f" Topic argument: {topic!r}." if topic else ""
        return (
            f"WORKFLOW MODE /{parsed.slash} — {parsed.description}\n"
            f"Read `.ai_agent_context/{parsed.slash}.md` immediately. "
            f"{_WORKFLOW_ROOT_HINT}\n"
            f"Optional: call MCP run_command with command={parsed.raw!r} "
            f"to confirm the contract path.{extra}"
        )
    if parsed.kind == "dispatcher":
        return (
            f"DISPATCHER /{parsed.slash} — {parsed.description}\n"
            f"Call MCP run_command with a subcommand "
            f"(e.g. /read index, /do sim 1.5). "
            f"/{parsed.slash} help lists every subcommand. "
            f"Do not use Shell."
        )
    args = ", ".join(f"{k}={v!r}" for k, v in parsed.kwargs.items())
    return (
        f"SLASH COMMAND DISPATCH — call this MCP tool immediately. "
        f"Do not use Shell. Do not ask the user to run it.\n"
        f"Command: {parsed.raw}\n"
        f"Preferred: run_command(command={parsed.raw!r})\n"
        f"Direct: {parsed.tool}({args})\n"
        f"{parsed.description}"
    )


_HOOK_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "prompt": handle_submit_prompt,
    "hook-prompt": handle_submit_prompt,
    "shell": handle_shell,
    "hook-shell": handle_shell,
    "mcp": handle_mcp_pre,
    "hook-mcp": handle_mcp_pre,
}


def hook_main(mode: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = _HOOK_HANDLERS.get(mode)
    if handler is None:
        return {"permission": "allow", "error": f"unknown hook mode {mode!r}"}
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
    try:
        return handler(payload)
    except Exception as exc:
        # Fail open — never block the agent because the catalog crashed.
        return {"permission": "allow", "continue": True, "error": str(exc)}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print("usage: python -m mcp_server.commands {parse,list,prompt,shell,mcp} [command]", file=sys.stderr)
        return 2
    mode = args[0]
    if mode == "parse":
        raw = " ".join(args[1:]) or sys.stdin.read()
        try:
            print(json.dumps(parse_command(raw).as_dict(), indent=2))
            return 0
        except CommandParseError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
    if mode == "list":
        print(json.dumps(list_catalog(), indent=2))
        return 0
    result = hook_main(mode)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
