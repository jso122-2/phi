# -*- coding: utf-8 -*-
"""phi.ui._app._navigation — page navigation and ML table switching.

CAIRRN scheduling
-----------------
Frame switch and on_show() are always synchronous — zero added latency.
root_pulse() runs after on_show() so the harmonic ring activation reflects
the fully-loaded page state.  The result gates follow-on expensive refresh
work (on_refresh) but never gates the initial frame show.

Latency contract:
    pack/pack_forget  → synchronous, immediate                 (Tk layout)
    on_show()         → synchronous, immediate                 (frame init)
    root_pulse()      → synchronous, after on_show             (CAIRRN signal)
    on_refresh()      → deferred via _sched(0, ...) only when hub is incoherent
"""
from __future__ import annotations


class _NavigationMixin:
    """go_to_page, toggle_rooms, ML table — page router."""

    def go_to_page(self, name: str) -> None:
        """Navigate directly to the named page (one of _page_names)."""
        if name not in self._page_frames:
            return

        # ── 1. Frame switch — always immediate ────────────────────────────────
        if self._in_ml_table:
            ml_name = self._ml_page_names[self._ml_page_idx]
            self._ml_page_frames[ml_name].pack_forget()
            self._in_ml_table = False
        else:
            old_name = self._page_names[self._page_idx]
            if old_name == name:
                return
            self._page_frames[old_name].pack_forget()

        self._page_idx = self._page_names.index(name)
        new_frame = self._page_frames[name]
        new_frame.pack(fill="both", expand=True)
        self._in_rooms = (name != "playing")

        label = "" if name == "playing" else f"  ·  {name.title()}"
        self.title(f"φ{label}")

        # ── 2. on_show() — always synchronous (frame must init before user sees it)
        if hasattr(new_frame, "on_show"):
            new_frame.on_show()

        # ── 3. CAIRRN root_pulse — informs the floor, then gates follow-on work
        result = self.floor.root_pulse(name)

        # Reset soot-ash state in the CAIRRN dispatcher — the user is navigating,
        # so any inherited tau-stretch from background ring activity should not
        # delay the next transport action.
        try:
            dispatcher = getattr(self, "cairrn_dispatcher", None)
            if dispatcher is not None:
                dispatcher.on_resume(0.0)
        except Exception:
            pass

        # ── 4. on_refresh — expensive rebuild only when hub is incoherent ─────
        if not result.coherent and hasattr(new_frame, "on_refresh"):
            self._sched(0, new_frame.on_refresh)

    def toggle_page(self, name: str) -> None:
        """Toggle between *name* and the now-playing page."""
        current = self._page_names[self._page_idx]
        if current == name:
            self.go_to_page("playing")
        else:
            self.go_to_page(name)

    def toggle_rooms(self) -> None:
        """e / k+s / ⌘/ — toggle between rooms and now-playing.

        If currently on the now-playing page, advances to the next room.
        If already in any room, returns to now-playing.
        """
        if self._in_z_spine:
            self._leave_z_spine()
            return
        if self._in_ml_table:
            self._leave_ml_table()
            return
        current = self._page_names[self._page_idx]
        if current != "playing":
            self.go_to_page("playing")
            return
        next_idx = (self._page_idx + 1) % len(self._page_names)
        if next_idx == 0:
            next_idx = 1
        self._page_idx = next_idx - 1
        self.go_to_page(self._page_names[next_idx])

    def toggle_ml_table(self) -> None:
        """⌘. — flip into / out of the ML page table."""
        if self._in_ml_table:
            self._leave_ml_table()
        else:
            self._enter_ml_table()

    def _enter_ml_table(self) -> None:
        """Switch from the normal page table into the ML page table."""
        old_name = self._page_names[self._page_idx]
        self._page_frames[old_name].pack_forget()
        self._in_ml_table = True
        self._in_rooms    = True
        name = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def _leave_ml_table(self) -> None:
        """Return from ML table to the now-playing page."""
        name = self._ml_page_names[self._ml_page_idx]
        self._ml_page_frames[name].pack_forget()
        self._in_ml_table = False
        self._in_rooms    = False
        self._page_idx    = 0
        self._page_frames["playing"].pack(fill="both", expand=True)
        self.title("φ")
        self.floor.root_pulse("playing")

    def ml_next_page(self) -> None:
        """Cycle forward through ML pages (dragon → inference → forge)."""
        if not self._in_ml_table:
            return
        old = self._ml_page_names[self._ml_page_idx]
        self._ml_page_frames[old].pack_forget()
        self._ml_page_idx = (self._ml_page_idx + 1) % len(self._ml_page_names)
        name = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def ml_prev_page(self) -> None:
        """Cycle backward through ML pages."""
        if not self._in_ml_table:
            return
        old = self._ml_page_names[self._ml_page_idx]
        self._ml_page_frames[old].pack_forget()
        self._ml_page_idx = (self._ml_page_idx - 1) % len(self._ml_page_names)
        name = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def navigate_shallower(self) -> None:
        """⌘↓ — step one level shallower (reverse of navigate_deeper).

        Depth order (each ⌘↓ press retreats one step):

            mixer → genre → playlist → library → queue → playing

        From playing, does nothing (already at the shallowest level).
        Inside the ML table, exits back to the last normal page.
        CAIRRN: same HOME-hub routing as navigate_deeper, full pressure.
        """
        if self._in_ml_table:
            self._leave_ml_table()
            self._cairrn_route_key("navigate_shallower", "HOME", 1.00)
            return

        current = self._page_names[self._page_idx]
        cur_idx = self._page_names.index(current)

        if cur_idx == 0:
            return

        self.go_to_page(self._page_names[cur_idx - 1])
        self._cairrn_route_key("navigate_shallower", "HOME", 1.00)

    def navigate_deeper(self) -> None:
        """⌘, — drill one level deeper through the page depth hierarchy.

        Depth order (each ⌘, press advances one step):

            playing → library → genre → playlist → mixer
                                                       ↓
              playing ←── ml_forge ←── ml_inference ←── ml_dragon

        From the last ML page (ml_forge) the next press exits back to playing,
        completing the full loop.  CAIRRN routes the move through HOME hub
        (topology navigation) at full pressure so the harmonic ring reflects
        the depth change immediately.
        """
        if self._in_ml_table:
            # Inside the ML table — advance to the next ML page.
            # If we're already on the last one, exit back to playing.
            next_idx = self._ml_page_idx + 1
            if next_idx >= len(self._ml_page_names):
                self._leave_ml_table()
            else:
                self.ml_next_page()
            self._cairrn_route_key("navigate_deeper", "agent-context", 0.60)
            return

        current  = self._page_names[self._page_idx]
        cur_idx  = self._page_names.index(current)
        next_idx = cur_idx + 1

        if next_idx >= len(self._page_names):
            # Past the last normal page → enter the ML table at its first page
            self._enter_ml_table()
            self._cairrn_route_key("navigate_deeper", "agent-context", 0.80)
        else:
            self.go_to_page(self._page_names[next_idx])
            self._cairrn_route_key("navigate_deeper", "HOME", 1.00)

    def _cairrn_route_key(self, action: str, hub: str, metric: float) -> None:
        """Fire CAIRRN side-effects for a navigation action (best-effort).

        Two effects per call:
          1. Route the action through PhiCairrnRouter.route_key() so the
             harmonic ring reflects the page context immediately.
          2. Call dispatcher.on_resume(0) to clear any inherited soot-ash
             HOT-phase state — the user is present and steering; stale
             tau-stretch from background ring activity must not penalise
             the next transport action.

        Previous implementation incorrectly resolved `cairrn_dispatcher`
        (a CAIRRNDispatcher) as the router — CAIRRNDispatcher has no
        route_key() method, so the call silently failed every time.
        The router lives at self.floor.router (a PhiCairrnRouter).
        """
        try:
            router = getattr(getattr(self, "floor", None), "router", None)
            if router is not None:
                router.route_key(action, hub, metric)
        except Exception:
            pass

        try:
            dispatcher = getattr(self, "cairrn_dispatcher", None)
            if dispatcher is not None:
                dispatcher.on_resume(0.0)
        except Exception:
            pass

    # ── Z-spine ───────────────────────────────────────────────────────────────

    def toggle_z_spine(self) -> None:
        """⌘Z — flip into / out of the z-spine page table."""
        if getattr(self, "_in_z_spine", False):
            self._leave_z_spine()
        else:
            self._enter_z_spine()

    def _enter_z_spine(self) -> None:
        """Switch from the normal page table into the z-spine."""
        if self._in_ml_table:
            self._leave_ml_table()

        old_name = self._page_names[self._page_idx]
        self._page_frames[old_name].pack_forget()
        self._in_z_spine = True
        self._in_rooms   = True

        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)
        self._cairrn_route_key("toggle_z_spine", "agent-context", 0.60)

    def _leave_z_spine(self) -> None:
        """Return from z-spine to the now-playing page."""
        name = self._z_page_names[self._z_page_idx]
        self._z_page_frames[name].pack_forget()
        self._in_z_spine = False
        self._in_rooms   = False
        self._page_idx   = 0
        self._page_frames["playing"].pack(fill="both", expand=True)
        self.title("φ")
        self.floor.root_pulse("playing")

    def z_next_page(self) -> None:
        """Cycle forward through z-spine pages."""
        if not getattr(self, "_in_z_spine", False):
            return
        old = self._z_page_names[self._z_page_idx]
        self._z_page_frames[old].pack_forget()
        self._z_page_idx = (self._z_page_idx + 1) % len(self._z_page_names)
        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)

    def z_prev_page(self) -> None:
        """Cycle backward through z-spine pages."""
        if not getattr(self, "_in_z_spine", False):
            return
        old = self._z_page_names[self._z_page_idx]
        self._z_page_frames[old].pack_forget()
        self._z_page_idx = (self._z_page_idx - 1) % len(self._z_page_names)
        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.title(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)
