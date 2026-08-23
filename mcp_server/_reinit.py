"""
Self-healing singleton re-init and watchdog retrigger.

Uses `import mcp_server._state as _st` (module reference) so attribute
assignments update the live module globals that late-importers see.
"""
from __future__ import annotations

import sys

import mcp_server._state as _st
from mcp_server._null_stubs import _NullDOMQueue, _NullVaultHub

_WARMUP_KEYS: tuple[str, ...] = ("warmup:phi", "warmup:corpus", "tools:retry")


def _reinit_harmonic() -> bool:
    """Rebuild HarmonicIndex + TicketClipper. Returns True on success."""
    with _st._lazy_lock:
        if _st._harmonic_index is not None:
            return True
        try:
            from sims.harmonic import HarmonicIndex, TicketClipper
            _st._harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
            _st._ticket_clipper = TicketClipper(_st._harmonic_index, threshold=0.01)
            _st.restore_harmonic_snapshot()
            _st.ensure_harmonic_warm()
            _st.startup_errors.pop("harmonic", None)
            print("[mcp_server._state] harmonic re-init: OK", file=sys.stderr)
            return True
        except Exception as exc:
            _st.startup_errors["harmonic"] = str(exc)
            print(f"[mcp_server._state] harmonic re-init failed: {exc}", file=sys.stderr)
            return False


def _reinit_temporal() -> bool:
    """Rebuild TemporalShardIndex. Returns True on success."""
    with _st._lazy_lock:
        if _st._temporal_index is not None:
            return True
        try:
            from sims.temporal import TemporalShardIndex
            _st._temporal_index = TemporalShardIndex(n_windows=8)
            _st.startup_errors.pop("temporal", None)
            print("[mcp_server._state] temporal re-init: OK", file=sys.stderr)
            return True
        except Exception as exc:
            _st.startup_errors["temporal"] = str(exc)
            print(f"[mcp_server._state] temporal re-init failed: {exc}", file=sys.stderr)
            return False


def _reinit_vault_hub() -> bool:
    """Rebuild VaultHub. Returns True on success."""
    from pathlib import Path
    with _st._lazy_lock:
        if not isinstance(_st._vault_hub, _NullVaultHub):
            return True
        try:
            from mcp_server.vault_hub import open_vault_hub
            _st._vault_hub = open_vault_hub(Path(__file__).parent.parent)
            _st.startup_errors.pop("vault_hub", None)
            print("[mcp_server._state] vault_hub re-init: OK", file=sys.stderr)
            return True
        except Exception as exc:
            _st.startup_errors["vault_hub"] = str(exc)
            print(f"[mcp_server._state] vault_hub re-init failed: {exc}", file=sys.stderr)
            return False


def _reinit_dom_queue() -> bool:
    """
    Rebuild DOMRequestQueue. Returns True on success.

    Also re-wires the _on_stall callback so future stalls trigger retrigger_warmups.
    """
    with _st._lazy_lock:
        if not isinstance(_st._dom_queue, _NullDOMQueue):
            return True
        try:
            from mcp_server.dom_queue import spawn_houses
            _st._dom_queue = spawn_houses()
            _st.startup_errors.pop("dom_queue", None)
            _st._dom_queue._on_stall = lambda _event: retrigger_warmups()  # type: ignore[attr-defined]
            print("[mcp_server._state] dom_queue re-init: OK", file=sys.stderr)
            return True
        except Exception as exc:
            _st.startup_errors["dom_queue"] = str(exc)
            print(f"[mcp_server._state] dom_queue re-init failed: {exc}", file=sys.stderr)
            return False


def _reinit_hot_loader() -> bool:
    """Rebuild CAIRRNHotLoader. Returns True on success."""
    with _st._lazy_lock:
        if _st._hot_loader is not None:
            return True
        try:
            from engine.hot_loader import CAIRRNHotLoader
            _st._hot_loader = CAIRRNHotLoader()
            _st.startup_errors.pop("hot_loader", None)
            print("[mcp_server._state] hot_loader re-init: OK", file=sys.stderr)
            return True
        except Exception as exc:
            _st.startup_errors["hot_loader"] = str(exc)
            print(f"[mcp_server._state] hot_loader re-init failed: {exc}", file=sys.stderr)
            return False


def _reinit_all_failed() -> dict[str, bool]:
    """
    Re-init every singleton currently in startup_errors.

    Called from retrigger_warmups() (watchdog stall) and from _startup_init()
    (manual recovery). Returns component → True (recovered) / False (still broken).
    """
    _REINIT_MAP = {
        "harmonic":   _reinit_harmonic,
        "temporal":   _reinit_temporal,
        "vault_hub":  _reinit_vault_hub,
        "dom_queue":  _reinit_dom_queue,
        "hot_loader": _reinit_hot_loader,
    }
    failed_keys = list(_st.startup_errors.keys())
    results: dict[str, bool] = {}
    for key in failed_keys:
        fn = _REINIT_MAP.get(key)
        if fn is not None:
            results[key] = fn()
    if results:
        recovered = [k for k, ok in results.items() if ok]
        still_broken = [k for k, ok in results.items() if not ok]
        if recovered:
            print(f"[mcp_server._state] re-init recovered: {recovered}", file=sys.stderr)
        if still_broken:
            print(f"[mcp_server._state] re-init still broken: {still_broken}", file=sys.stderr)
    return results


def retrigger_warmups() -> None:
    """
    Deadman fire: re-init failed singletons, invalidate warmup cache, kick
    CAIRRNHotLoader, and re-open the session gate.

    Called when RaceWatchdog records a stall.
    """
    _st._retrigger_count += 1
    _reinit_all_failed()

    if _st._hot_loader is not None:
        for name in _WARMUP_KEYS:
            _st._hot_loader.invalidate(name)
            _st._hot_loader.signal(name)
        _st._hot_loader.step()
    try:
        from mcp_server.bus.client import get_client
        client = get_client()
        if client is not None:
            client.submit("warmup.corpus", {})
            client.submit("warmup.phi", {})
    except Exception:
        pass
    try:
        from mcp_server._env_check import _startup_init
        _startup_init()
    except Exception as exc:
        print(f"[mcp_server._state] gate retrigger failed: {exc}", file=sys.stderr)
