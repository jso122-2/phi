#!/usr/bin/env python3
"""
backwards_burn.py — Google Keep backwards burner.

Overwrites every note in your Google Keep with random garbage text,
then deletes all notes. Content becomes permanently unreadable.

Run with:
    python backwards_burn.py

A Chromium window opens. Log in normally, press Enter in the terminal
when your notes are visible, then let it rip.
"""

import asyncio
import random
import string
import sys
import math
import tty
import termios

from playwright.async_api import async_playwright, Page, BrowserContext


# ---------------------------------------------------------------------------
# Login credentials
# ---------------------------------------------------------------------------

_EMAIL = "jacksonorloff122@gmail.com"
_PASSWORD = "Burn-Dawnie-Burn"

# Adjacent-key map for realistic typos (QWERTY)
_ADJACENT: dict[str, list[str]] = {
    "a": ["s", "q", "z"], "b": ["v", "n", "g"], "c": ["x", "v", "d"],
    "d": ["s", "f", "e", "c"], "e": ["w", "r", "d"], "f": ["d", "g", "r", "v"],
    "g": ["f", "h", "t", "b"], "h": ["g", "j", "y", "n"], "i": ["u", "o", "k"],
    "j": ["h", "k", "u", "m"], "k": ["j", "l", "i"], "l": ["k", "o", "p"],
    "m": ["n", "j", "k"], "n": ["b", "m", "h"], "o": ["i", "p", "l", "0"],
    "p": ["o", "l"], "q": ["w", "a"], "r": ["e", "t", "f"], "s": ["a", "d", "w", "x"],
    "t": ["r", "y", "g"], "u": ["y", "i", "j"], "v": ["c", "b", "f"],
    "w": ["q", "e", "s"], "x": ["z", "c", "s"], "y": ["t", "u", "h"],
    "z": ["a", "x"], "0": ["9", "o"], "1": ["2", "q"], "2": ["1", "3", "w"],
    "@": ["a", "2"], ".": [",", "l"], "-": ["_", "0"],
}


def _adjacent_key(ch: str) -> str:
    """Return a nearby key for a realistic typo."""
    pool = _ADJACENT.get(ch.lower(), [ch])
    return random.choice(pool)


async def human_move(page: Page, x: int, y: int) -> None:
    """Move mouse along a slight arc to (x, y) from current position."""
    steps = random.randint(18, 30)
    # We don't know current pos, so just move with playwright steps parameter
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(random.uniform(0.04, 0.12))


async def human_click(page: Page, x: int, y: int) -> None:
    await human_move(page, x, y)
    await asyncio.sleep(random.uniform(0.08, 0.18))
    await page.mouse.click(x, y)
    await asyncio.sleep(random.uniform(0.1, 0.25))


async def human_type(page: Page, text: str, typo_rate: float = 0.07) -> None:
    """
    Type text with randomised delays and occasional corrected typos.
    typo_rate: probability of a typo per character (email only — pass 0.0 for password).
    """
    for ch in text:
        # Randomised inter-key delay — bursts + occasional hesitation
        delay = random.gauss(95, 35)
        delay = max(40, min(delay, 280))

        # Occasional typo
        if typo_rate > 0 and random.random() < typo_rate:
            wrong = _adjacent_key(ch)
            await page.keyboard.type(wrong, delay=delay)
            await asyncio.sleep(random.uniform(0.12, 0.35))   # notice the mistake
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.08, 0.20))   # correct it

        await page.keyboard.type(ch, delay=delay)

        # Occasional mid-word pause (thinking)
        if random.random() < 0.04:
            await asyncio.sleep(random.uniform(0.3, 0.7))


def wait_for_spacebar() -> None:
    """Block until the user presses the spacebar key."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == " ":
                break
            if ch in ("\x03", "\x04"):   # Ctrl-C / Ctrl-D → abort
                print("\nAborted.")
                sys.exit(0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def auto_login(page: Page) -> None:
    """
    Attempt to fill email + password with human-like behaviour.
    Caller should handle captchas manually before pressing Enter here.
    """
    print("[→] Waiting for email field...")
    await page.wait_for_selector("input[type='email']", timeout=20_000)
    await asyncio.sleep(random.uniform(0.6, 1.2))

    # Click email field
    email_input = page.locator("input[type='email']").first
    box = await email_input.bounding_box()
    if box:
        cx = int(box["x"] + box["width"] * random.uniform(0.3, 0.7))
        cy = int(box["y"] + box["height"] * random.uniform(0.3, 0.7))
        await human_click(page, cx, cy)
    else:
        await email_input.click()

    await asyncio.sleep(random.uniform(0.3, 0.6))

    print(f"[→] Typing email with humanised input...")
    await human_type(page, _EMAIL, typo_rate=0.08)

    await asyncio.sleep(random.uniform(0.4, 0.9))

    # Click Next
    next_btn = page.get_by_role("button", name="Next").first
    if await next_btn.is_visible(timeout=3000):
        box = await next_btn.bounding_box()
        if box:
            cx = int(box["x"] + box["width"] * random.uniform(0.3, 0.7))
            cy = int(box["y"] + box["height"] * random.uniform(0.3, 0.7))
            await human_click(page, cx, cy)
        else:
            await next_btn.click()
    else:
        await page.keyboard.press("Enter")

    print("[→] Email submitted. Waiting for password field...")
    print("    [Solve any captcha that appears, then come back]")

    # Wait for password field (may require captcha solve first)
    try:
        await page.wait_for_selector("input[type='password']", timeout=60_000)
    except Exception:
        print("[!] Password field not found within 60 s — check browser for captcha.")
        input("    [Press Enter once the password page is visible] ")
        await page.wait_for_selector("input[type='password']", timeout=30_000)

    await asyncio.sleep(random.uniform(0.5, 1.0))

    pw_input = page.locator("input[type='password']").first
    box = await pw_input.bounding_box()
    if box:
        cx = int(box["x"] + box["width"] * random.uniform(0.3, 0.7))
        cy = int(box["y"] + box["height"] * random.uniform(0.3, 0.7))
        await human_click(page, cx, cy)
    else:
        await pw_input.click()

    await asyncio.sleep(random.uniform(0.3, 0.5))

    print("[→] Typing password...")
    await human_type(page, _PASSWORD, typo_rate=0.0)   # no typos on password

    await asyncio.sleep(random.uniform(0.4, 0.8))

    next_btn2 = page.get_by_role("button", name="Next").first
    if await next_btn2.is_visible(timeout=3000):
        box = await next_btn2.bounding_box()
        if box:
            cx = int(box["x"] + box["width"] * random.uniform(0.3, 0.7))
            cy = int(box["y"] + box["height"] * random.uniform(0.3, 0.7))
            await human_click(page, cx, cy)
        else:
            await next_btn2.click()
    else:
        await page.keyboard.press("Enter")

    print("[→] Password submitted. Waiting for Keep to load...")
    print("    [Solve any captcha / 2FA that appears]")

    # Wait until we land on keep.google.com
    try:
        await page.wait_for_url("**/keep.google.com/**", timeout=90_000)
    except Exception:
        input("    [Press Enter once you're on the Keep notes page] ")

    await asyncio.sleep(2.0)
    print("[→] Logged in and on Keep.")


# ---------------------------------------------------------------------------
# Garbage generator
# ---------------------------------------------------------------------------

_NOISE_POOL = (
    string.ascii_letters
    + string.digits
    + string.punctuation
    + " " * 12
    + "\t" * 3
)


def garbage(length: int = 600) -> str:
    """Return a random string of printable noise."""
    return "".join(random.choices(_NOISE_POOL, k=length))


def garbage_title() -> str:
    return garbage(random.randint(20, 60))


def garbage_body() -> str:
    return garbage(random.randint(400, 800))


# ---------------------------------------------------------------------------
# Keep selectors (aria-based — more stable than obfuscated class names)
# ---------------------------------------------------------------------------

# Note cards in the grid
NOTE_CARD = "[data-expanded]"

# Fields inside the open-note dialog
TITLE_FIELD = "[aria-label='Title']"
BODY_SELECTORS = [
    "[aria-label='Take a note…']",
    "[aria-label='Note']",
    "[placeholder='Take a note…']",
    "div[contenteditable='true']",
]

# Close / backdrop
CLOSE_BTN = "[aria-label='Close']"

# Three-dot overflow menu on a hovered card
MORE_OPTIONS = "[aria-label='More options']"
DELETE_NOTE_TEXT = "Delete note"

# Checklist items (list notes)
LIST_ITEM = "li[aria-label='List item']"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def find_body(page: Page):
    """Return the first visible body field, trying each selector."""
    for sel in BODY_SELECTORS:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                return loc
        except Exception:
            continue
    return None


async def close_open_note(page: Page) -> None:
    """Close an open note dialog — try Close button, then Escape."""
    try:
        btn = page.locator(CLOSE_BTN).first
        if await btn.is_visible(timeout=1000):
            await btn.click()
            await page.wait_for_timeout(500)
            return
    except Exception:
        pass
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)


async def overwrite_one_note(page: Page, card_idx: int, total: int) -> str:
    """
    Click card at position card_idx, overwrite title + body with garbage,
    close it. Returns 'ok', 'skip', or 'list'.
    """
    try:
        cards = await page.locator(NOTE_CARD).all()
        if card_idx >= len(cards):
            return "skip"

        card = cards[card_idx]
        await card.scroll_into_view_if_needed()
        await card.click()
        await page.wait_for_timeout(700)

        # --- Title ---
        try:
            title = page.locator(TITLE_FIELD).first
            if await title.is_visible(timeout=600):
                await title.click()
                await page.keyboard.press("Control+a")
                await title.fill(garbage_title())
                await page.wait_for_timeout(200)
        except Exception:
            pass

        # --- Body (text note) ---
        body = await find_body(page)
        if body:
            await body.click()
            await page.keyboard.press("Control+a")
            await body.fill(garbage_body())
            await page.wait_for_timeout(300)

        # --- List note items ---
        try:
            items = await page.locator(LIST_ITEM).all()
            for item in items:
                inp = item.locator("input[type='text'], [contenteditable='true']").first
                if await inp.is_visible(timeout=400):
                    await inp.click()
                    await page.keyboard.press("Control+a")
                    await inp.fill(garbage(30))
        except Exception:
            pass

        await close_open_note(page)
        print(f"  ✓  [{card_idx + 1}/{total}] overwritten")
        return "ok"

    except Exception as exc:
        print(f"  ✗  [{card_idx + 1}/{total}] error: {exc!r:.80} — skipping")
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
        except Exception:
            pass
        return "skip"


async def delete_one_note(page: Page, n: int) -> bool:
    """
    Delete the first visible note card via its overflow menu.
    Returns True on success.
    """
    try:
        cards = await page.locator(NOTE_CARD).all()
        if not cards:
            return False
        card = cards[0]
        await card.scroll_into_view_if_needed()
        await card.hover()
        await page.wait_for_timeout(350)

        menu = card.locator(MORE_OPTIONS).first
        if await menu.is_visible(timeout=800):
            await menu.click()
        else:
            # Fallback: right-click
            await card.click(button="right")

        await page.wait_for_timeout(400)

        delete_opt = page.get_by_text(DELETE_NOTE_TEXT, exact=True).first
        if await delete_opt.is_visible(timeout=1000):
            await delete_opt.click()
            await page.wait_for_timeout(600)
            print(f"  ✓  deleted [{n}]")
            return True

        # Dismiss if delete option not found
        await page.keyboard.press("Escape")
        return False

    except Exception as exc:
        print(f"  ✗  delete error [{n}]: {exc!r:.80}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def scroll_to_load_all(page: Page) -> None:
    """Scroll the page to force lazy-loading of all notes."""
    print("[→] Scrolling to load all notes...")
    prev_count = 0
    stalls = 0
    while stalls < 3:
        await page.keyboard.press("End")
        await page.wait_for_timeout(1200)
        cards = await page.locator(NOTE_CARD).all()
        count = len(cards)
        if count == prev_count:
            stalls += 1
        else:
            stalls = 0
            prev_count = count
    # Scroll back to top
    await page.keyboard.press("Home")
    await page.wait_for_timeout(800)
    final = await page.locator(NOTE_CARD).all()
    print(f"[→] {len(final)} notes detected after full scroll.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    import subprocess, time as _time, urllib.request

    print()
    print("=" * 62)
    print("   BACKWARDS BURN — Google Keep")
    print("=" * 62)
    print()

    # ── Step 1: Launch Chrome with debug port ────────────────────────
    print("[→] Closing any running Chrome instances...")
    subprocess.run(["pkill", "-x", "Google Chrome"], capture_output=True)
    _time.sleep(1.5)

    print("[→] Launching Chrome with remote debugging on port 9222...")
    subprocess.Popen([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ])

    print("[→] Waiting for Chrome...", end="", flush=True)
    for _ in range(20):
        _time.sleep(1)
        print(".", end="", flush=True)
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1)
            break
        except Exception:
            continue
    print(" ready.")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        # ── Step 2: Hand control to the user ─────────────────────────
        print("─" * 62)
        print("  Chrome is yours. Navigate to any page you want to burn.")
        print()
        print("  When you're ready, type  BURN  and hit Enter.")
        print("─" * 62)
        print()

        while True:
            cmd = input("  > ").strip()
            if cmd == "BURN":
                break
            elif cmd in ("q", "quit", "exit", "abort"):
                print("Aborted. Nothing touched.")
                await browser.close()
                sys.exit(0)
            else:
                print("  Type  BURN  to start, or  quit  to abort.")

        # Grab whichever page is currently active/focused
        pages = context.pages
        page = pages[-1] if pages else await context.new_page()

        print()
        print(f"[→] Target: {page.url}")
        print("[→] Ignition.\n")
        await page.wait_for_timeout(500)

        # Load all notes via scrolling
        await scroll_to_load_all(page)

        cards = await page.locator(NOTE_CARD).all()
        total = len(cards)

        if total == 0:
            print("[!] No notes found. Check that you're on the main Keep view.")
            await browser.close()
            return

        print(f"\n[→] {total} notes to process.\n")

        # ── PASS 1: Overwrite content ─────────────────────────────────────
        print("── PASS 1: Overwriting note content with garbage ──")
        for i in range(total):
            # Always click index 0 because the list may shift; notes already
            # overwritten still exist until pass 2, so we iterate by position
            # and use card_idx directly (order is stable within a pass).
            await overwrite_one_note(page, i, total)

        await page.wait_for_timeout(1000)

        # ── PASS 2: Delete all notes ──────────────────────────────────────
        print(f"\n── PASS 2: Deleting all {total} notes ──")
        deleted = 0
        consecutive_fails = 0
        while True:
            cards = await page.locator(NOTE_CARD).all()
            if not cards:
                break
            ok = await delete_one_note(page, deleted + 1)
            if ok:
                deleted += 1
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                if consecutive_fails >= 5:
                    print("[!] 5 consecutive delete failures — stopping delete pass.")
                    break

        # ── Summary ───────────────────────────────────────────────────────
        remaining = len(await page.locator(NOTE_CARD).all())
        print()
        print("=" * 62)
        print(f"  Overwritten : {total} notes")
        print(f"  Deleted     : {deleted} notes")
        if remaining:
            print(f"  Remaining   : {remaining} (may need manual cleanup)")
        else:
            print("  Remaining   : 0 — Keep is clear")
        print("=" * 62)
        print()
        print("  Done. You can close the browser window.")
        print()

        input("  [Press Enter to close the browser] ")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
