"""
phi/ui/app.py — phi player pygame desktop interface.

Replaces the former tkinter PhiApp.  Fully local — no server, no browser.

Architecture
------------
PhiTerminal owns the pygame window and runs an async game loop at 60 fps.
A 150 ms poll timer reads dispatcher / player state and refreshes the
displayed values each frame.  Transport buttons enqueue async tasks that
call astep() / aforce_dispatch() on the CAIRRN dispatcher.

Usage
-----
    from engine.phi_session import make_phi_session
    from phi.ui.app import run_phi_app

    session = make_phi_session(library_root="/path/to/music")
    session.build()
    run_phi_app(session)
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from typing import Any, Optional

import pygame
from engine.cairrn_dispatch import PhiAction, PhiActionKind

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (10,  10,  10)
BG2     = (18,  18,  18)
BG3     = (26,  26,  26)
GREEN   = (51,  255, 120)
AMBER   = (255, 176, 0)
PURPLE  = (190, 110, 255)
CYAN    = (0,   210, 210)
RED     = (255, 80,  80)
DIM     = (60,  60,  60)
WHITE   = (210, 210, 210)
GATE_ON = (51,  255, 120)
GATE_OFF= (255, 176, 0)

WIN_W, WIN_H = 520, 720
PAD = 14

# ── Hub → shard map (CAIRRN geometry) ────────────────────────────────────────
_HUB_SHARDS: dict[str, list[int]] = {
    "HOME":          [0],
    "MATH":          [1, 2],
    "CODE":          [3, 4],
    "COMMANDS":      [5],
    "agent-context": [6, 7],
}

# ── Play-fraction thresholds ──────────────────────────────────────────────────
FRAC_LOVED = 0.80
FRAC_HEARD = 0.40


# ── Helpers ───────────────────────────────────────────────────────────────────

def block_bar(value: float, width: int = 18) -> str:
    """Unicode block-character bar for a 0–1 value."""
    filled = round(max(0.0, min(1.0, value)) * width)
    return "█" * filled + "░" * (width - filled)


def lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── Button ────────────────────────────────────────────────────────────────────

class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        color: tuple,
        font: pygame.font.Font,
        enabled: bool = True,
    ) -> None:
        self.rect    = rect
        self.text    = text
        self.color   = color
        self.font    = font
        self.enabled = enabled
        self._hover  = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        col = self.color if self.enabled else DIM
        bg  = tuple(min(255, int(c * 0.18)) for c in col) if self.enabled else BG2
        hi  = tuple(min(255, int(c * 0.30)) for c in col) if self._hover and self.enabled else bg
        pygame.draw.rect(surface, hi, self.rect, border_radius=4)
        pygame.draw.rect(surface, col, self.rect, width=1, border_radius=4)
        lbl = self.font.render(self.text, True, col)
        surface.blit(lbl, (
            self.rect.centerx - lbl.get_width() // 2,
            self.rect.centery - lbl.get_height() // 2,
        ))


# ── Slider ────────────────────────────────────────────────────────────────────

class Slider:
    """Horizontal drag slider for play fraction."""

    def __init__(self, rect: pygame.Rect, value: float = 1.0) -> None:
        self.rect  = rect
        self.value = float(max(0.0, min(1.0, value)))
        self._drag = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._drag = True
                self._update(event.pos[0])
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        if event.type == pygame.MOUSEMOTION and self._drag:
            self._update(event.pos[0])

    def _update(self, x: int) -> None:
        rel = (x - self.rect.x) / max(1, self.rect.width)
        self.value = max(0.0, min(1.0, rel))

    def draw(self, surface: pygame.Surface) -> None:
        track = self.rect.inflate(0, -8)
        pygame.draw.rect(surface, BG3, track, border_radius=3)
        fill_w = int(track.width * self.value)
        if fill_w > 0:
            col = GATE_ON if self.value >= FRAC_LOVED else (AMBER if self.value >= FRAC_HEARD else RED)
            pygame.draw.rect(surface, col, (track.x, track.y, fill_w, track.height), border_radius=3)
        # Thumb
        thumb_x = self.rect.x + int(self.rect.width * self.value)
        pygame.draw.circle(surface, WHITE, (thumb_x, self.rect.centery), 7)
        pygame.draw.circle(surface, BG,   (thumb_x, self.rect.centery), 4)


# ── PhiTerminal ───────────────────────────────────────────────────────────────

class PhiTerminal:
    """
    Pygame frontend for the phi player pipeline.

    Parameters
    ----------
    pipeline : PhiPipeline — fully wired (make_phi_pipeline())
    fps      : render frame rate (default 60)
    poll_ms  : state-read interval in ms (default 150)
    """

    LOG_MAX  = 120
    POLL_S   = 0.15   # seconds between state reads

    def __init__(self, pipeline: Any, fps: int = 60, poll_ms: int = 150) -> None:
        self._pipeline = pipeline
        self._fps      = fps
        self._poll_s   = poll_ms / 1000.0

        pygame.init()
        pygame.display.set_caption("φ  player")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock  = pygame.time.Clock()

        self._font_lg = pygame.font.SysFont("Courier New", 20, bold=True)
        self._font    = pygame.font.SysFont("Courier New", 13)
        self._font_sm = pygame.font.SysFont("Courier New", 11)

        # Live state (updated by _poll)
        self._track_name   = "—"
        self._track_artist = "idle"
        self._track_idx    = ""
        self._coherence    = 0.0
        self._gate_open    = False
        self._hub_acts: dict[str, float] = {h: 0.0 for h in _HUB_SHARDS}
        self._plays        = 0
        self._skip_rate    = 0.0
        self._queue_depth  = 0
        self._log_lines: deque[str] = deque(maxlen=self.LOG_MAX)

        # Per-action debounce — prevent key+button double-fire within the watchdog window.
        # Kept separate so SEED doesn't get suppressed by a prior NEXT press.
        self._last_next_at: float = 0.0
        self._last_seed_at: float = 0.0

        self._build_widgets()

    # ── Widget construction ───────────────────────────────────────────────────

    def _build_widgets(self) -> None:
        f  = self._font
        fs = self._font_sm

        # Play-fraction slider — sits above transport buttons
        sl_y = WIN_H - 80 - PAD - 40 - PAD
        self._slider = Slider(pygame.Rect(PAD, sl_y, WIN_W - 2 * PAD, 30))

        # Transport buttons
        bw, bh = 114, 34
        btn_y  = WIN_H - 80 - PAD
        gap    = 8
        total  = 3 * bw + 2 * gap
        bx     = (WIN_W - total) // 2

        self._btn_next   = Button(pygame.Rect(bx,           btn_y, bw, bh), "⏭  NEXT",    GREEN,  f)
        self._btn_seed   = Button(pygame.Rect(bx + bw + gap, btn_y, bw, bh), "🌱  SEED",   PURPLE, f)
        self._btn_report = Button(pygame.Rect(bx+2*(bw+gap), btn_y, bw, bh), "✓  REPORT",  CYAN,   f)
        self._buttons    = [self._btn_next, self._btn_seed, self._btn_report]

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_n:
                    self._cmd_next()
                if event.key == pygame.K_r:
                    asyncio.create_task(self._do_report())
                if event.key == pygame.K_s:
                    self._cmd_seed()

            self._slider.handle_event(event)

            for btn in self._buttons:
                if btn.handle_event(event):
                    if btn is self._btn_next:
                        self._cmd_next()
                    elif btn is self._btn_seed:
                        self._cmd_seed()
                    elif btn is self._btn_report:
                        asyncio.create_task(self._do_report())

        return True

    # ── Transport — bus commands (synchronous enqueue, zero latency) ──────────

    def _cmd_next(self) -> None:
        """Force-dispatch SHUFFLE_NEXT — user button press bypasses the coherence gate.

        Button and keyboard presses are direct user commands; they must not
        queue behind the coherence rebuild.  force_dispatch() executes the
        action immediately and does not reset steps_since_tick, so the gate
        timeline is unaffected.

        A 450 ms per-action debounce (matching the DoubleRouteWatchdog window)
        prevents a simultaneous key-press + button-click from firing twice.
        """
        now = time.monotonic()
        if now - self._last_next_at < 0.45:
            return
        self._last_next_at = now
        try:
            self._pipeline.dispatcher.force_dispatch(
                PhiAction(PhiActionKind.SHUFFLE_NEXT, priority=-1)
            )
        except Exception as exc:
            self._log(f"!! next: {exc}")

    def _cmd_seed(self) -> None:
        """Enqueue SHUFFLE_SEED on the bus at urgent priority."""
        now = time.monotonic()
        if now - self._last_seed_at < 0.45:
            return
        self._last_seed_at = now
        try:
            self._pipeline.dispatcher.enqueue(
                PhiAction(PhiActionKind.SHUFFLE_SEED, priority=-1)
            )
            self._log("seed enqueued")
        except Exception as exc:
            self._log(f"!! seed enqueue: {exc}")

    # ── Transport — report (async: involves hub injection + propagation) ───────

    async def _do_report(self) -> None:
        """Report play fraction to the player; injects feedback via force_dispatch."""
        player = self._pipeline.player
        if not player._in_play:
            self._log("nothing in play — press NEXT first")
            return
        frac = self._slider.value
        try:
            ev = await asyncio.to_thread(player.report_play, frac)
            tag = "loved" if frac >= FRAC_LOVED else ("heard" if frac >= FRAC_HEARD else "skipped")
            self._log(
                f"  {tag}  {frac:.2f}  HOME={ev.home_injected:.3f}  CODE={ev.code_injected:.3f}"
            )
        except Exception as exc:
            self._log(f"!! report: {exc}")

    # ── Poll (reads pipeline state) ───────────────────────────────────────────

    def _poll(self) -> None:
        try:
            player     = self._pipeline.player
            dispatcher = self._pipeline.dispatcher
            session    = self._pipeline.session

            # Track
            track = player.current_track
            if track is not None:
                self._track_name   = getattr(track, "name", None) or track.stem or "—"
                self._track_artist = getattr(track, "artist", "") or ""
                idx = player._current_idx
                self._track_idx = f"idx {idx}" if idx is not None else ""
            else:
                self._track_name   = "—"
                self._track_artist = "idle"
                self._track_idx    = ""

            # Coherence
            self._coherence = dispatcher.coherence
            self._gate_open = dispatcher.gate_open

            # Hub activations
            idx_obj = getattr(session, "harmonic_index", None)
            if idx_obj is not None:
                shards = idx_obj.shards
                for hub, shard_ids in _HUB_SHARDS.items():
                    vals = [shards[i].activation for i in shard_ids if i < len(shards)]
                    self._hub_acts[hub] = sum(vals) / len(vals) if vals else 0.0

            # Stats
            self._plays       = player.total_plays
            self._skip_rate   = player.skip_rate
            self._queue_depth = dispatcher.queue_depth

        except Exception:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self) -> None:
        s   = self.screen
        f   = self._font
        fsm = self._font_sm
        flg = self._font_lg
        s.fill(BG)

        x, y = PAD, PAD

        # ── φ header ──────────────────────────────────────────────────────────
        phi_lbl = flg.render("φ", True, PURPLE)
        pl_lbl  = f.render("  PLAYER", True, DIM)
        s.blit(phi_lbl, (x, y))
        s.blit(pl_lbl,  (x + phi_lbl.get_width(), y + 4))
        y += phi_lbl.get_height() + 8

        # ── Now playing card ──────────────────────────────────────────────────
        card_h = 72
        card_r = pygame.Rect(PAD, y, WIN_W - 2 * PAD, card_h)
        pygame.draw.rect(s, BG2, card_r, border_radius=4)
        pygame.draw.rect(s, BG3, card_r, width=1, border_radius=4)

        hdr = fsm.render("NOW PLAYING", True, DIM)
        s.blit(hdr, (card_r.x + 8, card_r.y + 6))

        tn = f.render(self._track_name[:48], True, WHITE)
        s.blit(tn, (card_r.x + 8, card_r.y + 20))

        ta = fsm.render(self._track_artist[:48], True, DIM)
        s.blit(ta, (card_r.x + 8, card_r.y + 38))

        ti = fsm.render(self._track_idx, True, DIM)
        s.blit(ti, (card_r.right - ti.get_width() - 8, card_r.y + 38))

        y += card_h + 10

        # ── Coherence / gate ──────────────────────────────────────────────────
        coh_card = pygame.Rect(PAD, y, WIN_W - 2 * PAD, 58)
        pygame.draw.rect(s, BG2, coh_card, border_radius=4)
        pygame.draw.rect(s, BG3, coh_card, width=1, border_radius=4)

        gate_col = GATE_ON if self._gate_open else GATE_OFF
        gate_txt = "GATE  OPEN" if self._gate_open else "GATE  CLOSED"
        gh = fsm.render("CAIRRN COHERENCE", True, DIM)
        gg = fsm.render(gate_txt, True, gate_col)
        s.blit(gh, (coh_card.x + 8, coh_card.y + 6))
        s.blit(gg, (coh_card.right - gg.get_width() - 8, coh_card.y + 6))

        # Bar
        bar_rect = pygame.Rect(coh_card.x + 8, coh_card.y + 24, coh_card.width - 16, 10)
        pygame.draw.rect(s, BG3, bar_rect, border_radius=3)
        fill_w = int(bar_rect.width * self._coherence)
        if fill_w > 0:
            pygame.draw.rect(s, gate_col, (bar_rect.x, bar_rect.y, fill_w, bar_rect.height), border_radius=3)

        coh_v = fsm.render(f"{self._coherence:.4f}", True, gate_col)
        s.blit(coh_v, (coh_card.x + 8, coh_card.y + 40))

        y += 58 + 10

        # ── Hub activations ───────────────────────────────────────────────────
        hub_card_h = 14 + len(_HUB_SHARDS) * 22 + 8
        hub_card = pygame.Rect(PAD, y, WIN_W - 2 * PAD, hub_card_h)
        pygame.draw.rect(s, BG2, hub_card, border_radius=4)
        pygame.draw.rect(s, BG3, hub_card, width=1, border_radius=4)

        hdr2 = fsm.render("HUB ACTIVATIONS", True, DIM)
        s.blit(hdr2, (hub_card.x + 8, hub_card.y + 6))

        hy = hub_card.y + 20
        for hub, act in self._hub_acts.items():
            lbl  = fsm.render(f"{hub:<14}", True, DIM)
            bar  = fsm.render(block_bar(act, 14), True, lerp_color(DIM, GREEN, act))
            val  = fsm.render(f"{act:.3f}", True, DIM)
            s.blit(lbl,  (hub_card.x + 8,                          hy))
            s.blit(bar,  (hub_card.x + 8 + lbl.get_width() + 4,    hy))
            s.blit(val,  (hub_card.right - val.get_width() - 8,     hy))
            hy += 22

        y += hub_card_h + 10

        # ── Stats ─────────────────────────────────────────────────────────────
        stat_h = 28
        stat_card = pygame.Rect(PAD, y, WIN_W - 2 * PAD, stat_h)
        pygame.draw.rect(s, BG2, stat_card, border_radius=4)

        stats_txt = (
            f"plays: {self._plays}    "
            f"skip: {self._skip_rate:.2f}    "
            f"queue: {self._queue_depth}"
        )
        st = fsm.render(stats_txt, True, DIM)
        s.blit(st, (stat_card.x + 8, stat_card.centery - st.get_height() // 2))

        y += stat_h + 10

        # ── Log ───────────────────────────────────────────────────────────────
        btn_area   = 34 + PAD + 40 + PAD + PAD  # slider + buttons + margins
        log_h      = WIN_H - y - btn_area
        log_rect   = pygame.Rect(PAD, y, WIN_W - 2 * PAD, max(40, log_h))
        pygame.draw.rect(s, BG2, log_rect, border_radius=4)

        line_h  = fsm.get_height() + 2
        visible = log_rect.height // line_h
        lines   = list(self._log_lines)[-visible:]
        for i, line in enumerate(lines):
            surf = fsm.render(line[:80], True, DIM)
            s.blit(surf, (log_rect.x + 6, log_rect.y + 4 + i * line_h))

        # ── Slider ────────────────────────────────────────────────────────────
        # Label
        frac_col = GATE_ON if self._slider.value >= FRAC_LOVED else (AMBER if self._slider.value >= FRAC_HEARD else RED)
        sl_lbl   = fsm.render(f"play fraction: {self._slider.value:.2f}", True, frac_col)
        s.blit(sl_lbl, (PAD, self._slider.rect.y - sl_lbl.get_height() - 2))
        self._slider.draw(s)

        # ── Transport buttons ─────────────────────────────────────────────────
        kbd_hint = fsm.render("n=next  r=report  s=seed  esc=quit", True, DIM)
        s.blit(kbd_hint, ((WIN_W - kbd_hint.get_width()) // 2, WIN_H - 16))

        for btn in self._buttons:
            btn.draw(s)

        pygame.display.flip()

    # ── Log helper ────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        self._log_lines.append(msg)

    # ── Main async loop ───────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Two concurrent tasks:

        tick_task  — calls dispatcher.run_tick_loop() at poll_ms cadence.
                     Owns all step() calls; never blocks the render path.
        render loop — handles events + draws at fps cadence using
                      asyncio.sleep() so the event loop stays unblocked.
                      clock.tick(0) measures elapsed time without sleeping.
        """
        stop = asyncio.Event()
        frame_s = 1.0 / self._fps

        tick_task = asyncio.create_task(
            self._pipeline.dispatcher.run_tick_loop(
                interval_s=self._poll_s,
                stop_event=stop,
            )
        )

        try:
            running = True
            while running:
                dt_ms = self.clock.tick(0)   # non-blocking — just measures elapsed ms
                running = self.handle_events()
                self._poll()                  # cheap property reads, no lock held
                self.draw()
                # Sleep for whatever is left of the frame budget
                sleep_s = max(0.0, frame_s - dt_ms / 1000.0)
                await asyncio.sleep(sleep_s)
        finally:
            stop.set()
            tick_task.cancel()
            try:
                await tick_task
            except asyncio.CancelledError:
                pass

        pygame.quit()


# ── Entry point ───────────────────────────────────────────────────────────────

def run_phi_app(
    session: Any,
    *,
    fps: int = 60,
    poll_ms: int = 150,
    hover_regions: list | None = None,
) -> None:
    """
    Wire a built PhiTracerSession into the phi pygame player and launch.

    Parameters
    ----------
    session       : PhiTracerSession — session.build() must already be called
    fps           : render frame rate (default 60)
    poll_ms       : state-read interval in ms (default 150)
    hover_regions : optional list of HoverRegion for cursor-hover prefetch
    """
    from engine.phi_player import make_phi_pipeline

    pipeline = make_phi_pipeline(
        session=session,
        hover_regions=hover_regions or [],
    )

    terminal = PhiTerminal(pipeline=pipeline, fps=fps, poll_ms=poll_ms)

    asyncio.run(terminal.run())


# Backwards compat alias
run_phi_terminal = run_phi_app
