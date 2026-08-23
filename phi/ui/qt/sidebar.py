# -*- coding: utf-8 -*-
"""phi.ui.qt.sidebar — PySide6 sidebar panel.

Replaces phi.ui.sidebar.SidebarPanel.

Starts hidden (same as the Tk version).  Press the sidebar hotkey (⌘B) to
reveal it.  The execute_cmd logic is preserved verbatim — only the Tkinter
display layer (tk.Text + tk.Entry) is replaced with QTextBrowser + QLineEdit.

Public API (mirrors SidebarPanel)
-----------------------------------
    update_queue(queue, pos, library)
    update_info(path, meta, ann)
    execute_cmd(raw) -> str
    focus_repl()
    toggle()
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, FG, MUTED, fmt_time

_W   = 27
_SEP = "─" * _W

_TAG_COLORS: dict[str, str] = {
    "acc":    ACC,
    "warm":   FG,
    "dim":    MUTED,
    "header": ACC2,
    "now":    ACC,
    "fb":     ACC,
}


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


class SidebarWidget(QWidget):
    """
    Left sidebar with ASCII queue / info / cmd display + REPL entry.

    Starts hidden; toggle() shows/hides it in the parent layout.
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl     = ctrl
        self._visible  = False
        self._feedback = ""

        self._queue_lines: list[tuple[str, str]] = []
        self._info_lines:  list[tuple[str, str]] = []
        self._history:     list[str] = []
        self._hist_pos     = -1

        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._clear_feedback)

        self.setFixedWidth(224)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._build()
        self.hide()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._display = QTextEdit()
        self._display.setReadOnly(True)
        self._display.setFont(self._display.font())
        self._display.setStyleSheet(
            f"background: {BG}; color: {MUTED}; border: none; "
            f"font-family: Menlo, Courier, monospace; font-size: 9px;"
        )
        self._display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._display, stretch=1)

        # separator
        sep_line = QWidget()
        sep_line.setFixedHeight(1)
        sep_line.setStyleSheet(f"background: {ACC2};")
        root.addWidget(sep_line)

        # REPL row
        repl = QWidget()
        repl.setStyleSheet(f"background: {CARD};")
        repl_layout = QHBoxLayout(repl)
        repl_layout.setContentsMargins(4, 4, 4, 4)
        repl_layout.setSpacing(4)

        prompt = QLabel("φ >")
        prompt.setStyleSheet(
            f"color: {ACC}; font-family: Menlo, monospace; font-size: 9px;"
        )
        self._entry = QLineEdit()
        self._entry.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; "
            f"font-family: Menlo, monospace; font-size: 9px;"
        )
        self._entry.returnPressed.connect(self._on_enter)

        repl_layout.addWidget(prompt)
        repl_layout.addWidget(self._entry, stretch=1)
        root.addWidget(repl)

        self._render()

    # ── public API ─────────────────────────────────────────────────────────────

    def update_queue(self, queue: list[int], pos: int, library: object) -> None:
        lines: list[tuple[str, str]] = []
        start = max(0, pos - 1)
        end   = min(len(queue), start + 8)

        for qi in range(start, end):
            pl_idx = queue[qi]
            path   = library.playlist[pl_idx]  # type: ignore[attr-defined]
            name   = _trunc(library.display_name(path), _W - 8)  # type: ignore[attr-defined]
            num    = f"{qi + 1:>3}."
            prefix = "▶" if qi == pos else " "
            tag    = "now" if qi == pos else "dim"
            lines.append((f" {prefix} {num}  {name}", tag))

        if not lines:
            lines.append(("  (empty)", "dim"))

        rem = sum(
            float((library.get_meta(library.playlist[queue[qi]]) or {}).get("duration") or 0)  # type: ignore[attr-defined]
            for qi in range(pos, min(len(queue), pos + 200))  # cap lookahead — avoids O(n) SQLite reads
        )
        if rem > 0:
            h, m = int(rem) // 3600, (int(rem) % 3600) // 60
            rem_s = f"{h}h {m}m" if h else f"{m}m"
            lines.append(("", "dim"))
            lines.append((f"  ∞ {rem_s} remaining", "header"))

        self._queue_lines = lines
        self._render()

    def update_info(self, path: str, meta: dict | None, ann: dict | None) -> None:
        meta  = meta or {}
        ann   = ann  or {}
        stats = self._ctrl.library.get_stats(path) if path else {}  # type: ignore[attr-defined]
        lines: list[tuple[str, str]] = []

        dur  = meta.get("duration")
        bpm  = ann.get("bpm") or meta.get("bpm")
        key  = ann.get("key") or meta.get("key")
        mood = ann.get("mood")
        ext  = os.path.splitext(path)[1].upper().lstrip(".") if path else ""

        def row(label: str, value: object, pending: bool = False) -> tuple[str, str]:
            val_s = str(value) if value is not None else "──"
            if pending:
                val_s = "pending"
            return (f"  {label:<5} ──  {_trunc(val_s, _W - 12)}", "dim" if pending else "warm")

        if meta.get("title"):
            lines.append((_trunc(f"  {meta['title']}", _W), "warm"))
        if meta.get("artist"):
            lines.append((_trunc(f"  {meta['artist']}", _W), "dim"))

        rating = stats.get("rating", 0)
        plays  = stats.get("plays", 0)
        if rating or plays:
            stars = "★" * rating + "☆" * (5 - rating)
            lines.append((f"  {stars}  ▶ {plays}", "acc" if rating else "dim"))

        lines.append(("", "dim"))
        lines.append(row("dur",  fmt_time(dur) if dur else None))
        lines.append(row("bpm",  f"{bpm:.0f}" if isinstance(bpm, float) and bpm else bpm,
                         pending=not bpm))
        lines.append(row("key",  key, pending=not key))
        lines.append(row("mood", mood, pending=not mood))
        if ext:
            lines.append(row("fmt", ext))

        self._info_lines = lines
        self._render()

    def execute_cmd(self, raw: str) -> str:
        """Parse raw and execute the corresponding player action.  Returns feedback."""
        cmd  = raw.strip()
        low  = cmd.lower()
        ctrl = self._ctrl
        lib  = ctrl.library  # type: ignore[attr-defined]

        if low in ("n", "next"):
            ctrl.on_next();          return "→ next"  # type: ignore[attr-defined]
        if low in ("p", "prev"):
            ctrl.on_prev();          return "← prev"  # type: ignore[attr-defined]
        if low in ("stop", "s"):
            ctrl.on_stop();          return "■ stopped"  # type: ignore[attr-defined]
        if low in ("pause", "play"):
            ctrl.on_play_pause();    return "⏯ toggled"  # type: ignore[attr-defined]
        if low == "shuffle":
            ctrl.on_toggle_shuffle(); return "⇀ shuffle toggled"  # type: ignore[attr-defined]
        if low == "clear":
            ctrl.on_clear();         return "× queue cleared"  # type: ignore[attr-defined]

        if low.startswith("vol "):
            try:
                v = float(low[4:]) / 100.0
                ctrl.on_volume(max(0.0, min(1.0, v)))  # type: ignore[attr-defined]
                return f"[V] {int(v * 100)}%"
            except ValueError:
                return "? vol <0–100>"

        if low.startswith("play ") and ":" not in low[5:]:
            try:
                n = int(low[5:]) - 1
                if 0 <= n < len(ctrl.queue.queue):  # type: ignore[attr-defined]
                    ctrl._load_and_play(n)           # type: ignore[attr-defined]
                    return f"▶ track {n + 1}"
            except ValueError:
                pass

        if low.startswith("play artist:"):
            artist = cmd[12:].strip()
            tracks = lib.tracks_by_artist(artist)
            if not tracks:
                matches = [a for a in lib.artists() if artist.lower() in a.lower()]
                if matches:
                    tracks = lib.tracks_by_artist(matches[0])
                    artist = matches[0]
            if tracks:
                ctrl.on_play_path(tracks[0])           # type: ignore[attr-defined]
                ctrl.tabs.switch_to("tracks")          # type: ignore[attr-defined]
                return f"▶ {_trunc(artist, 18)}"
            return "? artist not found"

        if low.startswith("play album:"):
            query = cmd[11:].strip().lower()
            for artist, album, _ in lib.albums():
                if query in album.lower():
                    tracks = lib.tracks_by_album(artist, album)
                    if tracks:
                        ctrl.on_play_album(tracks)     # type: ignore[attr-defined]
                        ctrl.tabs.switch_to("tracks")  # type: ignore[attr-defined]
                        return f"▶ {_trunc(album, 18)}"
            return "? album not found"

        if low.startswith("queue artist:"):
            artist = cmd[13:].strip()
            tracks = lib.tracks_by_artist(artist)
            if not tracks:
                matches = [a for a in lib.artists() if artist.lower() in a.lower()]
                if matches:
                    tracks = lib.tracks_by_artist(matches[0])
                    artist = matches[0]
            new = lib.add(tracks)
            if new:
                ctrl.queue.rebuild(lib.size, keep_current=True)  # type: ignore[attr-defined]
                ctrl._rebuild_view()                              # type: ignore[attr-defined]
            return f"+ {len(tracks)} tracks by {_trunc(artist, 10)}"

        if low.startswith("queue album:"):
            query = cmd[12:].strip().lower()
            for artist, album, _ in lib.albums():
                if query in album.lower():
                    tracks = lib.tracks_by_album(artist, album)
                    new = lib.add(tracks)
                    if new:
                        ctrl.queue.rebuild(lib.size, keep_current=True)  # type: ignore[attr-defined]
                        ctrl._rebuild_view()                              # type: ignore[attr-defined]
                    return f"+ {len(tracks)} tracks — {_trunc(album, 12)}"
            return "? album not found"

        if low.startswith("filter "):
            q = cmd[7:].strip()
            ctrl.playlist_panel.search_var.set(q)  # type: ignore[attr-defined]
            ctrl.tabs.switch_to("tracks")          # type: ignore[attr-defined]
            return f"⌕ {_trunc(q, 18)}"

        if low.startswith("save "):
            name = cmd[5:].strip().replace(" ", "_")
            if not name:
                return "? save <playlist-name>"
            default_path = os.path.expanduser(f"~/Music/{name}.m3u")
            ctrl._write_m3u(default_path)  # type: ignore[attr-defined]
            return f"sv {name}.m3u"

        if low.startswith("route ") or low.startswith("page "):
            dest = low.split(None, 1)[1].strip()
            _aliases = {
                "playing": "playing", "home": "playing", "now": "playing",
                "library": "library", "bookcase": "library", "books": "library",
                "genre":   "genre",   "genres":   "genre",
                "playlist": "playlist", "playlists": "playlist",
                "mixer": "mixer", "mix": "mixer",
            }
            resolved = _aliases.get(dest)
            if resolved and hasattr(ctrl, "go_to_page"):
                ctrl.go_to_page(resolved)       # type: ignore[attr-defined]
                label = resolved if resolved != "playing" else "now playing"
                return f"→ {label}"
            return "? route <playing · library · genre · playlist · mixer>"

        if low.startswith("goto ") or low.startswith("jump "):
            try:
                n = int(low.split()[1]) - 1
                if 0 <= n < len(ctrl.queue.queue):  # type: ignore[attr-defined]
                    ctrl._load_and_play(n)           # type: ignore[attr-defined]
                    return f"▶ track {n + 1}"
            except (ValueError, IndexError):
                pass
            return "? goto <n>"

        if low.startswith("rate "):
            try:
                stars = int(low[5:])
                cur = ctrl.queue.current_playlist_idx  # type: ignore[attr-defined]
                if cur >= 0:
                    path = ctrl.library.playlist[cur]  # type: ignore[attr-defined]
                    ctrl.library.set_rating(path, stars)  # type: ignore[attr-defined]
                    ann  = ctrl.library.get_annotation(path)  # type: ignore[attr-defined]
                    self.update_info(path, ctrl.library.get_meta(path), ann)  # type: ignore[attr-defined]
                    return f"★ {stars}/5"
            except ValueError:
                return "? rate <0-5>"

        if low == "discover":
            ctrl.tabs.switch_to("discover"); return "→ discover tab"  # type: ignore[attr-defined]
        if low == "info":
            ctrl.tabs.switch_to("artists");  return "→ artists tab"   # type: ignore[attr-defined]
        if low == "enrich":
            ctrl.tabs.switch_to("enrich");   return "→ enrich tab"    # type: ignore[attr-defined]

        if low == "similar" or low.startswith("similar "):
            try:
                n = int(low.split()[1]) if " " in low else 10
            except (ValueError, IndexError):
                n = 10
            cur = ctrl.queue.current_playlist_idx  # type: ignore[attr-defined]
            if cur < 0:
                return "? nothing playing"
            path = ctrl.library.playlist[cur]  # type: ignore[attr-defined]
            from phi.core.similarity import find_similar
            matches = find_similar(path, ctrl.library, n=n)
            if not matches:
                return "? no vectors yet — run Models first"
            new_paths = [p for p, _ in matches]
            ctrl.library.add(new_paths)            # type: ignore[attr-defined]
            ctrl.queue.rebuild(ctrl.library.size, keep_current=True)  # type: ignore[attr-defined]
            ctrl._rebuild_view()                   # type: ignore[attr-defined]
            ctrl._flash(f"∿ {len(new_paths)} similar tracks queued")  # type: ignore[attr-defined]
            return f"∿ {len(new_paths)} similar"

        if low == "radio" or low.startswith("radio "):
            try:
                n = int(low.split()[1]) if " " in low else 20
            except (ValueError, IndexError):
                n = 20
            cur = ctrl.queue.current_playlist_idx  # type: ignore[attr-defined]
            if cur < 0:
                return "? nothing playing"
            path = ctrl.library.playlist[cur]  # type: ignore[attr-defined]
            from phi.core.similarity import build_radio
            playlist = build_radio(path, ctrl.library, length=n)
            if not playlist:
                return "? no vectors yet — run Models first"
            ctrl.library.add(playlist)             # type: ignore[attr-defined]
            ctrl.queue.rebuild(ctrl.library.size, keep_current=True)  # type: ignore[attr-defined]
            ctrl._rebuild_view()                   # type: ignore[attr-defined]
            ctrl._flash(f"◎ radio: {n} tracks")   # type: ignore[attr-defined]
            return f"◎ radio {n} tracks"

        if low in ("picker", "picker on", "picker off"):
            if low == "picker on":
                ctrl.picker_enabled = True         # type: ignore[attr-defined]
            elif low == "picker off":
                ctrl.picker_enabled = False        # type: ignore[attr-defined]
            else:
                ctrl.picker_enabled = not ctrl.picker_enabled  # type: ignore[attr-defined]
            state = "on" if ctrl.picker_enabled else "off"  # type: ignore[attr-defined]
            ctrl._flash(f"Track picker: {state}")  # type: ignore[attr-defined]
            return f"picker {state}"

        if low == "help":
            return "play/queue/filter/vol/shuffle/clear/similar/radio/route/enrich/picker"

        return f"? {_trunc(low, 20)}"

    def focus_repl(self) -> None:
        self._entry.setFocus()

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()
        self._visible = not self._visible

    # ── rendering ──────────────────────────────────────────────────────────────

    def _render(self) -> None:
        self._display.clear()
        cursor = self._display.textCursor()

        def _fmt(tag: str) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(_TAG_COLORS.get(tag, MUTED)))
            return fmt

        def hdr(label: str) -> None:
            pad = _W - len(label) - 3
            text = f"─ {label} {'─' * max(0, pad)}\n"
            cursor.insertText(text, _fmt("header"))

        def sep() -> None:
            cursor.insertText(_SEP + "\n", _fmt("dim"))

        hdr("φ  queue")
        for line, tag in self._queue_lines:
            cursor.insertText(line + "\n", _fmt(tag))
        sep()

        hdr("φ  info")
        for line, tag in self._info_lines:
            cursor.insertText(line + "\n", _fmt(tag))
        sep()

        hdr("φ  cmd")
        hints = [
            "  play artist:<n>",
            "  play album:<n>",
            "  filter <query>",
            "  vol <0-100>",
            "  shuffle · clear",
            "  save <name>",
        ]
        for h in hints:
            cursor.insertText(_trunc(h, _W) + "\n", _fmt("dim"))

        if self._feedback:
            cursor.insertText("\n", _fmt("dim"))
            cursor.insertText(f"  {self._feedback}\n", _fmt("fb"))

    # ── REPL handlers ──────────────────────────────────────────────────────────

    def _on_enter(self) -> None:
        raw = self._entry.text().strip()
        if not raw:
            return
        self._history.insert(0, raw)
        self._hist_pos = -1
        self._entry.clear()

        result = self.execute_cmd(raw)
        self._feedback = result
        self._render()
        self._feedback_timer.start(3_000)

    def _clear_feedback(self) -> None:
        self._feedback = ""
        self._render()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up and self._entry.hasFocus():
            if self._history:
                self._hist_pos = min(self._hist_pos + 1, len(self._history) - 1)
                self._entry.setText(self._history[self._hist_pos])
            return
        super().keyPressEvent(event)
