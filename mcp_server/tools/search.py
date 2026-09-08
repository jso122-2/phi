"""Search / RAG tools: psspps_query, find_query.

PSSPPS is the MCP search function.  Live harmonic-index state modulates
perspective_alpha (how local vs global retrieval is) unless the caller
overrides it.  This is the MCP analogue of phi.engine.vault_context's
basin-sequestration → alpha mapping.

Cloud Agents attach ``python3 -m mcp_server.cloud`` as stdio MCP ``phi`` and
MUST call these tools instead of running ``psspps.find`` / ``run_psspps``
ad hoc.  When the mmap bus is down, ``submit_and_maybe_wait`` executes the
same bus tasks in-process.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from mcp_server._gate import requires_init
from mcp_server._state import _adaptive_confidence, _dom_queue, _harmonic_index, mcp
from mcp_server.bus.client import submit_and_maybe_wait
from psspps.find import FIND_MODES
from psspps.scorer import _structural_order, modulate_search_alpha


def _search_control(
    activations: np.ndarray,
    perspective_alpha: float | None,
    t_b_norm: float | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Decide the blend weight that will drive this search.

    None  → index modulates (peaked shards → local/harmonic, diffuse → global).
    float → caller override, still clipped to [0, 1].

    When a vault-topology fusion has stored t_b_norm, blend it 50/50 with
    the index alpha so retrieval locality tracks χ/β₁ even on a cold ring.
    """
    from graph.topology_index import t_b_to_alpha

    index_alpha = modulate_search_alpha(activations)
    topo_alpha: float | None = None
    if t_b_norm is not None:
        topo_alpha = t_b_to_alpha(float(t_b_norm))

    if perspective_alpha is not None:
        alpha = float(np.clip(perspective_alpha, 0.0, 1.0))
        source = "caller"
    elif topo_alpha is not None:
        alpha = 0.5 * index_alpha + 0.5 * topo_alpha
        source = "index+topology"
    else:
        alpha = index_alpha
        source = "index"

    total = float(np.abs(activations).sum())
    if total < 1e-12:
        order = 0.0
        peak = 0
    else:
        order = _structural_order(np.abs(activations) / total)
        peak = int(np.argmax(np.abs(activations)))

    return alpha, {
        "perspective_alpha": round(alpha, 4),
        "source":            source,
        "index_alpha":       round(index_alpha, 4),
        "t_b_norm":          None if t_b_norm is None else round(float(t_b_norm), 4),
        "t_b_alpha":         None if topo_alpha is None else round(topo_alpha, 4),
        "structural_order":  round(order, 4),
        "peak_shard":        peak,
        "total_activation":  round(total, 4),
    }


@mcp.tool()
@requires_init
def psspps_query(
    query: str,
    top_k: int = 3,
    perspective_alpha: float | None = None,
    wait_s: float = 30.0,
) -> dict[str, Any]:
    """
    Run a PSSPPS query against the Obsidian knowledge vault.

    Retrieval runs on the mmap/celery bus. Alpha is computed here from the
    live harmonic index.

    Parameters
    ----------
    query             : natural-language question or search string
    top_k             : top-ranked documents to return (default 3)
    perspective_alpha : None = index-modulated.
                        0.0 = pure semantic | 1.0 = pure harmonic.
    wait_s            : seconds to wait for the worker (0 = return job_id)
    """
    with _dom_queue.gate("psspps_query"):
        activations = _harmonic_index.activation_vector()
        alpha, modulation = _search_control(
            activations, perspective_alpha, _harmonic_index.last_t_b_norm,
        )
        # TODO: K injection — after bus result lands, compute K from top result's
        # tag coherence and inject into content's home hub shards.
        return submit_and_maybe_wait(
            "search.psspps",
            wait_s=wait_s,
            query=query,
            activations=activations.tolist(),
            top_k=top_k,
            perspective_alpha=float(alpha),
            modulation=modulation,
        )


@mcp.tool()
@requires_init
def find_query(query: str, mode: str = "pericles", wait_s: float = 30.0) -> dict[str, Any]:
    """
    /find — vault retrieval with four selectable retrieval modes.

    Retrieval runs on the mmap/celery bus.

    Parameters
    ----------
    query  : keyword or natural-language search string
    mode   : one of "pericles" | "semantic" | "harmonic" | "quick"
    wait_s : seconds to wait for the worker (0 = return job_id)
    """
    if mode not in FIND_MODES:
        return {
            "error":       "unknown_mode",
            "mode":        mode,
            "valid_modes": sorted(FIND_MODES),
        }

    with _dom_queue.gate("find_query"):
        activations = _harmonic_index.activation_vector()
        idx_state = _harmonic_index.state()
        alpha, modulation = _search_control(
            activations, None, _harmonic_index.last_t_b_norm,
        )
        override = alpha if mode in ("pericles", "quick") else None

        # Session DAWN confidence floor — K = |Tcv| - SHI computed live.
        # Tcv = CAIRRN self-judged coherence from last hub run (0.5 when cold).
        # SHI = mean shard activation. dawn_x = max(|K * 0| ∨ 0, 0) simplified
        # to just K clamped ≥ 0, since j' and drift are session-level constants.
        _tcv = _adaptive_confidence()
        _shi = float(activations.mean()) if activations.size > 0 else 0.0
        _K   = abs(_tcv) - _shi
        dawn_x = max(_K, 0.0)

        return submit_and_maybe_wait(
            "search.find",
            wait_s=wait_s,
            query=query,
            activations=activations.tolist(),
            mode=mode,
            harmonic_step=int(idx_state.get("step", 0)),
            perspective_alpha=override,
            modulation=modulation,
            dawn_x=dawn_x,
        )
