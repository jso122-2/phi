# -*- coding: utf-8 -*-
"""
phi.ui.style — immutable stylesheet (phi's single source of CSS truth).

This module is the ONE place where every colour in the UI is defined.
Think of it as the CSS :root { --var: value; } block.

Rules
-----
1. Every colour used anywhere in phi MUST come from this file.
2. No hardcoded hex strings are permitted in UI files.
3. The palette is frozen at import time — mutating PALETTE raises
   FrozenInstanceError at runtime; type-checkers enforce Final.
4. To change a colour: edit the default value in PhiPalette below,
   nowhere else.

Usage
-----
    from phi.ui.style import BG, ACC, CARD, FG          # preferred shorthand
    from phi.ui.style import PALETTE                     # full typed object

Palette map (visual reference)
-------------------------------

    BG      ████  #09090e  near-black         — window / page background
    CARD    ████  #2c2d3a  gunmetal grey      — panels, boxes, lists
    CARD2   ████  #1a1b25  deep gunmetal      — troughs, secondary surfaces
    BORDER  ████  #16172a  subtle border      — 1 px dividers

    ACC     ████  #9b5de5  purple             — primary accent, highlights
    GOLD    ████  #c4a35a  gold               — trim on accented elements
    ACC2    ████  #4a3880  deep indigo-violet — selection bg, secondary

    INDIGO  ████  #5c6bc0  indigo             — graph labels, crumb hints
    VIOLET  ████  #7c4dce  violet             — bright contrast

    FG      ████  #f0ead8  bone white         — all body text
    MUTED   ████  #9490b5  lavender-grey      — secondary / dimmed text
    NOW     ████  #9b5de5  purple (= ACC)     — now-playing row highlight

    METER_OK   ██  #3ecf8e  green  — compatible BPM/key transition
    METER_WARN ██  #c4a35a  gold   — moderate mismatch (= GOLD)
    METER_CRIT ██  #e05472  red    — harsh / incompatible transition

    ENTRY_BG ████  #2c2d3a  gunmetal  — Entry / Listbox backgrounds (= CARD)
    ENTRY_FG ████  #f0ead8  bone white — Entry / Listbox text (= FG)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class PhiPalette:
    """
    Immutable colour palette.

    frozen=True means any attempted mutation raises FrozenInstanceError.
    All fields use typing.Final at the module level so type-checkers
    also reject accidental reassignments.

    Do not instantiate this directly — use the module-level PALETTE singleton.
    """

    # ── backing ───────────────────────────────────────────────────────────────
    bg:     str = "#09090e"    # near-black — window and page background

    # ── surfaces (gunmetal grey family) ───────────────────────────────────────
    card:   str = "#2c2d3a"    # gunmetal — all panels, boxes, list backgrounds
    card2:  str = "#1a1b25"    # deep gunmetal — secondary surfaces, slider troughs
    border: str = "#16172a"    # subtle 1 px dividers

    # ── accents ───────────────────────────────────────────────────────────────
    acc:    str = "#9b5de5"    # purple — primary accent (buttons, highlights, now-playing)
    gold:   str = "#c4a35a"    # gold — trim on accented elements, warm highlights
    acc2:   str = "#4a3880"    # deep indigo-violet — secondary accent, selection bg

    # ── contrast colour family ────────────────────────────────────────────────
    indigo: str = "#5c6bc0"    # indigo — graph labels, crumb hints
    violet: str = "#7c4dce"    # violet — bright contrast

    # ── text ─────────────────────────────────────────────────────────────────
    fg:     str = "#f0ead8"    # bone white — all body text
    muted:  str = "#9490b5"    # lavender-grey — secondary / dimmed text
    now:    str = "#9b5de5"    # now-playing row highlight (= acc)

    # ── semantic meter colours (mixer BPM/key compatibility) ──────────────────
    meter_ok:   str = "#3ecf8e"    # green — compatible transition
    meter_warn: str = "#c4a35a"    # gold  — moderate mismatch (= gold)
    meter_crit: str = "#e05472"    # red   — harsh / incompatible transition

    # ── input widgets ─────────────────────────────────────────────────────────
    # macOS Aqua may override Entry bg to white, so we keep entry_fg legible
    # on both the forced-white and our intended gunmetal surfaces.
    entry_bg: str = "#2c2d3a"    # gunmetal — Entry / Listbox backgrounds (= card)
    entry_fg: str = "#f0ead8"    # bone white — Entry / Listbox text (= fg)


# ── singleton ─────────────────────────────────────────────────────────────────

PALETTE: Final = PhiPalette()
"""The one and only palette instance. Read-only at both the type and runtime level."""


# ── flat aliases (import these in UI files) ───────────────────────────────────
# These are Final so mypy / pyright will reject any attempted reassignment.
# They exist purely for ergonomics — `from phi.ui.style import BG, ACC` is
# shorter than `from phi.ui.style import PALETTE; PALETTE.bg`.

BG:         Final[str] = PALETTE.bg
CARD:       Final[str] = PALETTE.card
CARD2:      Final[str] = PALETTE.card2
BORDER:     Final[str] = PALETTE.border
ACC:        Final[str] = PALETTE.acc
GOLD:       Final[str] = PALETTE.gold
ACC2:       Final[str] = PALETTE.acc2
INDIGO:     Final[str] = PALETTE.indigo
VIOLET:     Final[str] = PALETTE.violet
FG:         Final[str] = PALETTE.fg
MUTED:      Final[str] = PALETTE.muted
NOW:        Final[str] = PALETTE.now
METER_OK:   Final[str] = PALETTE.meter_ok
METER_WARN: Final[str] = PALETTE.meter_warn
METER_CRIT: Final[str] = PALETTE.meter_crit
ENTRY_BG:   Final[str] = PALETTE.entry_bg
ENTRY_FG:   Final[str] = PALETTE.entry_fg


# ── public API ────────────────────────────────────────────────────────────────

__all__ = [
    # The full typed palette object
    "PALETTE",
    "PhiPalette",
    # Flat aliases — import these in UI files
    "BG",
    "CARD",
    "CARD2",
    "BORDER",
    "ACC",
    "GOLD",
    "ACC2",
    "INDIGO",
    "VIOLET",
    "FG",
    "MUTED",
    "NOW",
    "METER_OK",
    "METER_WARN",
    "METER_CRIT",
    "ENTRY_BG",
    "ENTRY_FG",
]
