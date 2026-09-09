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


def seed_hot_loader() -> None:
    """
    Register the startup warmup corpus in CAIRRNHotLoader and fire the first step.

    Without this call, _hot_loader.total stays 0 at startup.  Every
    retrigger_warmups() then signals keys that have never been registered —
    the signal() calls all return False, step() touches nothing, and misses
    accumulate silently.

    Three entries are registered:
      warmup:corpus  — pre-loads the PSSPPS vault retriever corpus
      warmup:phi     — pre-builds the PhiTracerSession (phi_clip warm-up)
      tools:retry    — retries any singleton that failed at startup
    """
    if _st._hot_loader is None:
        return

    # Only register entries that aren't already loaded (idempotent on re-call).
    if _st._hot_loader.is_ready("warmup:corpus") and \
       _st._hot_loader.is_ready("warmup:phi"):
        return

    def _load_corpus() -> dict:
        try:
            from psspps.retriever import get_vault_corpus
            corpus = get_vault_corpus()
            n = getattr(corpus, "n_docs", None)
            print(f"[hot_loader] warmup:corpus loaded (n_docs={n})", file=sys.stderr)
            return {"warmed": "corpus", "n_docs": n}
        except Exception as exc:
            print(f"[hot_loader] warmup:corpus failed: {exc}", file=sys.stderr)
            return {"warmed": "corpus", "error": str(exc)}

    def _load_phi() -> object:
        try:
            from mcp_server.tools.phi_clip import warmup_phi_clip
            session = warmup_phi_clip()
            if session is not None:
                print("[hot_loader] warmup:phi loaded — phi_clip is warm", file=sys.stderr)
            else:
                print(
                    "[hot_loader] warmup:phi: library absent — phi_clip_ready will stay false",
                    file=sys.stderr,
                )
            return session
        except Exception as exc:
            print(f"[hot_loader] warmup:phi failed: {exc}", file=sys.stderr)
            return None

    def _load_tools_retry() -> dict:
        try:
            return _reinit_all_failed()
        except Exception as exc:
            print(f"[hot_loader] tools:retry failed: {exc}", file=sys.stderr)
            return {}

    _st._hot_loader.register(
        "warmup:corpus",
        signal_fn=lambda: True,
        load_fn=_load_corpus,
    )
    _st._hot_loader.register(
        "warmup:phi",
        signal_fn=lambda: True,
        load_fn=_load_phi,
    )
    _st._hot_loader.register(
        "tools:retry",
        signal_fn=lambda: bool(_st.startup_errors),
        load_fn=_load_tools_retry,
    )
    _st._hot_loader.step()
    print(
        f"[mcp_server._reinit] hot_loader seeded "
        f"({len(_st._hot_loader)} entries, step fired)",
        file=sys.stderr,
    )


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
