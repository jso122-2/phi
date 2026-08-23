#!/usr/bin/env python3
"""
burn_gui.py — Google Keep Backwards Burner
Pygame desktop GUI (fully local, no browser/server).

Flow:
  LAUNCH     → kills Chrome, relaunches with real profile + CDP
  ⊕ TARGET  → confirm you're on the right Keep page
  START BURN → overwrites every note with garbage, then deletes all
  ABORT      → stops cleanly after current note

Run:
    python scripts/burn_gui.py
"""

import asyncio
import glob
import os
import random
import string
import subprocess
import sys
import urllib.request
from collections import deque
from typing import Optional

import pygame
from playwright.async_api import async_playwright, Browser, Page

# ── Config ────────────────────────────────────────────────────────────────────
CHROME_BIN     = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_PROFILE = "/Users/jacksonmacleod/Library/Application Support/Google/Chrome"
CDP_PORT       = 9222
TARGET_URL     = "https://keep.google.com/u/1/"
SCREENSHOT_DIR = os.path.dirname(os.path.abspath(__file__))

WIN_W, WIN_H = 720, 600

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (13,  13,  13)
BG2     = (20,  20,  20)
BG3     = (26,  26,  26)
GREEN   = (51,  255, 80)
DGREEN  = (20,  100, 35)
AMBER   = (255, 176, 0)
RED     = (255, 60,  60)
CYAN    = (0,   210, 210)
DIM     = (70,  70,  70)
WHITE   = (210, 210, 210)
PURPLE  = (180, 100, 255)

# ── Note probes ───────────────────────────────────────────────────────────────
_NOTE_PROBES = [
    "[role='listitem'][jsaction]",
    "[role='option']",
    "[data-expanded]",
    "[data-tags]",
    "div[jscontroller][data-tags]",
    "div[jsaction*='mouseenter'][jscontroller]",
]

# ── Garbage generator ─────────────────────────────────────────────────────────
_POOL = string.ascii_letters + string.digits + string.punctuation + "   "

def garbage(n: int = 600) -> str:
    return "".join(random.choices(_POOL, k=n))


# ── Keep page helpers ─────────────────────────────────────────────────────────

async def detect_note_selector(page: Page, log) -> Optional[str]:
    best_sel, best_n = None, 0
    for sel in _NOTE_PROBES:
        try:
            n = await page.locator(sel).count()
            log(f"probe {sel!r} → {n}")
            if n > best_n:
                best_n, best_sel = n, sel
        except Exception:
            pass
    if best_sel:
        log(f"using selector: {best_sel!r} ({best_n} notes)")
    else:
        log("!! no note selector matched")
    return best_sel


async def find_body(page: Page):
    for sel in [
        "[aria-label='Note']",
        "[aria-label='Take a note…']",
        "div[contenteditable='true'][spellcheck]",
        "div[contenteditable='true']",
    ]:
        try:
            loc = page.locator(sel).last
            if await loc.is_visible(timeout=500):
                return loc
        except Exception:
            pass
    return None


async def close_note(page: Page) -> None:
    try:
        btn = page.locator("[aria-label='Close']").first
        if await btn.is_visible(timeout=600):
            await btn.click()
            await page.wait_for_timeout(350)
            return
    except Exception:
        pass
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(350)


async def overwrite_note(page: Page, note_sel: str, idx: int, total: int) -> bool:
    try:
        cards = await page.locator(note_sel).all()
        if idx >= len(cards):
            return False
        await cards[idx].scroll_into_view_if_needed()
        await cards[idx].click()
        await page.wait_for_timeout(600)
        try:
            t = page.locator("[aria-label='Title']").first
            if await t.is_visible(timeout=400):
                await t.click()
                await page.keyboard.press("Control+a")
                await t.fill(garbage(40))
        except Exception:
            pass
        body = await find_body(page)
        if body:
            await body.click()
            await page.keyboard.press("Control+a")
            await body.fill(garbage(600))
        await page.wait_for_timeout(200)
        await close_note(page)
        return True
    except Exception:
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(250)
        except Exception:
            pass
        return False


async def delete_first_note(page: Page, note_sel: str) -> bool:
    try:
        cards = await page.locator(note_sel).all()
        if not cards:
            return False
        await cards[0].scroll_into_view_if_needed()
        await cards[0].hover()
        await page.wait_for_timeout(280)
        menu = cards[0].locator("[aria-label='More options']").first
        if await menu.is_visible(timeout=600):
            await menu.click()
        else:
            await cards[0].click(button="right")
        await page.wait_for_timeout(300)
        opt = page.get_by_text("Delete note", exact=True).first
        if await opt.is_visible(timeout=700):
            await opt.click()
            await page.wait_for_timeout(420)
            return True
        await page.keyboard.press("Escape")
        return False
    except Exception:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def scroll_load_all(page: Page, note_sel: str, log) -> int:
    log("scrolling to load all notes...")
    prev, stalls = 0, 0
    while stalls < 3:
        await page.keyboard.press("End")
        await page.wait_for_timeout(900)
        n = await page.locator(note_sel).count()
        stalls = stalls + 1 if n == prev else 0
        prev = n
    await page.keyboard.press("Home")
    await page.wait_for_timeout(400)
    total = await page.locator(note_sel).count()
    log(f"{total} notes loaded")
    return total


# ── Core burn coroutine ───────────────────────────────────────────────────────

async def run_burn(
    log,
    set_status,
    set_note_count,
    set_progress,
    target_event: asyncio.Event,
    go_event: asyncio.Event,
    abort_event: asyncio.Event,
) -> None:
    log("closing existing Chrome...")
    subprocess.run(["pkill", "-x", "Google Chrome"], capture_output=True)
    await asyncio.sleep(1.5)

    log("launching Chrome with your real session...")
    subprocess.Popen([
        CHROME_BIN,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={CHROME_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
    ])

    log("waiting for CDP port...")
    for _ in range(30):
        await asyncio.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
            log("CDP port open")
            break
        except Exception:
            pass
    else:
        log("!! CDP never opened")
        return

    async with async_playwright() as pw:
        try:
            browser: Browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        except Exception as exc:
            log(f"!! connect failed: {exc}")
            return

        ctx = browser.contexts[0] if browser.contexts else None
        if not ctx:
            log("!! no browser context found")
            return

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        log(f"navigating to {TARGET_URL}")
        set_status("NAVIGATING")
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        note_sel = await detect_note_selector(page, log)
        if note_sel is None:
            log("!! could not detect note selector")
            await browser.close()
            return

        n = await page.locator(note_sel).count()
        set_note_count(n)
        log(f"landed on Keep — {n} notes visible")
        set_status(f"READY  ·  {n} notes — click  ⊕ TARGET  to lock")

        log("waiting for target lock...")
        while not target_event.is_set() and not abort_event.is_set():
            try:
                n = await page.locator(note_sel).count()
                set_note_count(n)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if abort_event.is_set():
            log("aborted before target lock")
            await browser.close()
            return

        target_event.clear()
        n = await page.locator(note_sel).count()
        set_note_count(n)
        log(f"TARGET LOCKED — {n} notes")
        set_status(f"LOCKED  ·  {n} notes — click  START BURN")

        while not go_event.is_set() and not abort_event.is_set():
            await asyncio.sleep(0.3)

        if abort_event.is_set():
            log("aborted before burn")
            await browser.close()
            return

        go_event.clear()

        total = await scroll_load_all(page, note_sel, log)
        if total == 0:
            log("!! no notes found")
            await browser.close()
            return

        log(f"PASS 1 — overwriting {total} notes")
        set_status(f"PASS 1/2  overwriting {total} notes...")
        for i in range(total):
            if abort_event.is_set():
                log("aborted during overwrite")
                break
            ok = await overwrite_note(page, note_sel, i, total)
            log(f"{'OK' if ok else 'XX'}  [{i + 1}/{total}]")
            set_progress((i + 1) / (total * 2))

        log("PASS 2 — deleting all notes")
        set_status("PASS 2/2  deleting...")
        deleted, fails = 0, 0
        while not abort_event.is_set():
            if await page.locator(note_sel).count() == 0:
                break
            ok = await delete_first_note(page, note_sel)
            if ok:
                deleted += 1
                fails = 0
                log(f"DEL [{deleted}]")
                set_progress(0.5 + min(deleted, total) / total * 0.5)
            else:
                fails += 1
                if fails >= 5:
                    log("!! 5 consecutive delete failures — stopping")
                    break

        try:
            for old in glob.glob(os.path.join(SCREENSHOT_DIR, "burn-*.png")):
                os.remove(old)
            shot = os.path.join(SCREENSHOT_DIR, "burn-complete.png")
            await page.screenshot(path=shot, full_page=False)
            log("screenshot saved: burn-complete.png")
        except Exception as exc:
            log(f"(screenshot failed: {exc})")

        log(f"DONE — {deleted}/{total} notes destroyed")
        set_status(f"COMPLETE  ·  {deleted}/{total} destroyed  ·  Keep is empty")
        set_progress(1.0)
        await asyncio.sleep(2)
        await browser.close()


# ── Pygame UI ─────────────────────────────────────────────────────────────────

class Button:
    """Simple pygame button."""

    def __init__(self, rect: pygame.Rect, text: str, color: tuple, font: pygame.font.Font):
        self.rect    = rect
        self.text    = text
        self.color   = color
        self.font    = font
        self.enabled = True
        self._hover  = False

    def set_enabled(self, val: bool) -> None:
        self.enabled = val

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        col = self.color if self.enabled else DIM
        border_col = tuple(min(255, c + 40) for c in col) if self._hover and self.enabled else col
        pygame.draw.rect(surface, BG3, self.rect, border_radius=3)
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=3)
        label = self.font.render(self.text, True, col if self.enabled else DIM)
        lx = self.rect.centerx - label.get_width() // 2
        ly = self.rect.centery - label.get_height() // 2
        surface.blit(label, (lx, ly))


class BurnGUI:
    """Pygame implementation of the burn GUI."""

    LOG_MAX = 200
    FONT_SIZE = 13
    PAD = 12

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("backwards-burn  //  keep")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock  = pygame.time.Clock()

        self.font      = pygame.font.SysFont("Courier New", self.FONT_SIZE)
        self.font_bold = pygame.font.SysFont("Courier New", 18, bold=True)
        self.font_sm   = pygame.font.SysFont("Courier New", 11)

        # Async events — shared with run_burn()
        self._target_event = asyncio.Event()
        self._go_event     = asyncio.Event()
        self._abort_event  = asyncio.Event()

        # Mutable UI state
        self._status     = "IDLE  —  press  [ LAUNCH ]"
        self._note_count = "--"
        self._progress   = 0.0
        self._log_lines: deque[str] = deque(maxlen=self.LOG_MAX)
        self._phase      = "idle"   # idle | launched | targeted | burning | done

        self._build_buttons()

    # ── Button layout ─────────────────────────────────────────────────────────

    def _build_buttons(self) -> None:
        bw, bh = 148, 34
        by = WIN_H - bh - self.PAD
        gap = 10
        total_w = 4 * bw + 3 * gap
        bx = (WIN_W - total_w) // 2

        self.btn_launch = Button(pygame.Rect(bx,               by, bw, bh), "[ LAUNCH ]",     GREEN, self.font)
        self.btn_target = Button(pygame.Rect(bx + bw + gap,    by, bw, bh), "[ ⊕ TARGET ]",  CYAN,  self.font)
        self.btn_burn   = Button(pygame.Rect(bx + 2*(bw+gap),  by, bw, bh), "[ START BURN ]", RED,   self.font)
        self.btn_abort  = Button(pygame.Rect(bx + 3*(bw+gap),  by, bw, bh), "[ ABORT ]",      DIM,   self.font)

        self.btn_target.set_enabled(False)
        self.btn_burn.set_enabled(False)
        self.btn_abort.set_enabled(False)

        self._buttons = [self.btn_launch, self.btn_target, self.btn_burn, self.btn_abort]

    # ── State callbacks (called from run_burn coroutine) ──────────────────────

    def log(self, msg: str) -> None:
        self._log_lines.append(msg)

    def set_status(self, msg: str) -> None:
        self._status = msg

    def set_note_count(self, n: int) -> None:
        self._note_count = str(n)

    def set_progress(self, v: float) -> None:
        self._progress = float(max(0.0, min(1.0, v)))

    # ── Button click handlers ─────────────────────────────────────────────────

    def _on_launch(self) -> None:
        if self._phase != "idle":
            return
        self._phase = "launched"
        self.btn_launch.set_enabled(False)
        self.btn_target.set_enabled(True)
        self.btn_abort.set_enabled(True)
        self._abort_event.clear()
        self._target_event.clear()
        self._go_event.clear()
        asyncio.create_task(
            run_burn(
                self.log, self.set_status, self.set_note_count, self.set_progress,
                self._target_event, self._go_event, self._abort_event,
            )
        )
        self.log("burn task started")

    def _on_target(self) -> None:
        if self._phase != "launched":
            return
        self._phase = "targeted"
        self.btn_target.set_enabled(False)
        self.btn_burn.set_enabled(True)
        self._target_event.set()
        self.log("⊕  target locked")

    def _on_burn(self) -> None:
        if self._phase != "targeted":
            return
        self._phase = "burning"
        self.btn_burn.set_enabled(False)
        self.log("ignition")
        self._go_event.set()

    def _on_abort(self) -> None:
        self._abort_event.set()
        self._target_event.set()
        self._go_event.set()
        self._phase = "idle"
        self.btn_abort.set_enabled(False)
        self.set_status("ABORTED")
        self.log("abort signal sent")
        # Reset for re-use
        self.btn_launch.set_enabled(True)
        self.btn_target.set_enabled(False)
        self.btn_burn.set_enabled(False)

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        """Process pygame events. Returns False when window should close."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

            for btn in self._buttons:
                if btn.handle_event(event):
                    if btn is self.btn_launch:
                        self._on_launch()
                    elif btn is self.btn_target:
                        self._on_target()
                    elif btn is self.btn_burn:
                        self._on_burn()
                    elif btn is self.btn_abort:
                        self._on_abort()
        return True

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self) -> None:
        s = self.screen
        P = self.PAD
        s.fill(BG)

        # ── Title bar ─────────────────────────────────────────────────────────
        pygame.draw.rect(s, BG2, (0, 0, WIN_W, 38))
        title = self.font_bold.render("[ backwards-burn ]", True, GREEN)
        s.blit(title, (P, 10))
        sub = self.font_sm.render("google keep  //  full destruction", True, DIM)
        s.blit(sub, (P + title.get_width() + 16, 16))

        # ── Status row ────────────────────────────────────────────────────────
        y_status = 46
        pygame.draw.rect(s, BG3, (0, y_status, WIN_W, 28))
        lbl = self.font_sm.render(" STATUS >", True, DGREEN)
        s.blit(lbl, (P, y_status + 7))
        st = self.font_sm.render(self._status, True, AMBER)
        s.blit(st, (P + lbl.get_width() + 6, y_status + 7))
        nc = self.font_sm.render(f"notes: {self._note_count}", True, CYAN)
        s.blit(nc, (WIN_W - nc.get_width() - P, y_status + 7))

        # ── Progress bar ──────────────────────────────────────────────────────
        bar_y = 74
        bar_h = 5
        pygame.draw.rect(s, BG2, (0, bar_y, WIN_W, bar_h))
        fill_w = int(WIN_W * self._progress)
        if fill_w > 0:
            pygame.draw.rect(s, GREEN, (0, bar_y, fill_w, bar_h))

        # ── Log area ──────────────────────────────────────────────────────────
        log_y     = bar_y + bar_h + P
        btn_area  = 34 + P + P       # button row height + margins
        log_h     = WIN_H - log_y - btn_area - P
        log_rect  = pygame.Rect(P, log_y, WIN_W - 2 * P, log_h)
        pygame.draw.rect(s, BG2, log_rect, border_radius=3)

        line_h = self.font_sm.get_height() + 2
        visible = log_h // line_h
        lines   = list(self._log_lines)[-visible:]
        for i, line in enumerate(lines):
            surf = self.font_sm.render(line[:110], True, GREEN)
            s.blit(surf, (log_rect.x + 6, log_rect.y + 4 + i * line_h))

        # ── Buttons ───────────────────────────────────────────────────────────
        for btn in self._buttons:
            btn.draw(s)

        # ── Footer ────────────────────────────────────────────────────────────
        foot = self.font_sm.render(
            "launch → navigate → ⊕ lock target → start burn", True, DIM
        )
        s.blit(foot, ((WIN_W - foot.get_width()) // 2, WIN_H - 14))

        pygame.display.flip()

    # ── Main async loop ───────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Render at ~60 fps using asyncio.sleep() for frame pacing.

        clock.tick(0) measures elapsed time without blocking the event loop.
        asyncio.sleep() yields to the loop so run_burn() coroutine progresses
        between frames without being starved.
        """
        frame_s = 1.0 / 60
        running = True
        while running:
            dt_ms   = self.clock.tick(0)   # non-blocking elapsed measurement
            running = self.handle_events()
            self.draw()
            sleep_s = max(0.0, frame_s - dt_ms / 1000.0)
            await asyncio.sleep(sleep_s)

        pygame.quit()


# ── Entry point ───────────────────────────────────────────────────────────────

async def _main() -> None:
    gui = BurnGUI()
    await gui.run()


if __name__ == "__main__":
    asyncio.run(_main())
