# -*- coding: utf-8 -*-
"""Entry point: python -m phi

Architecture
────────────
PhiMainWindow (PySide6 QMainWindow) owns the audio engine, session
persistence, media keys, enrichment daemons, and all UI panels.  It runs
on the main thread, which AppKit / NSWindow requires on macOS.

Two QTimer-based drain loops service the internal queues:
  phi-dispatch — enrichment / metadata callbacks (~32 ms, idle-stops)
  phi-poll     — media keys, sleep timer, AVPlayer callbacks (~16 ms, idle-stops)

Both are started inside PhiMainWindow.__init__ via _start_drain_threads().
They run only while work is queued — empty ticks stop the timer.
"""
from __future__ import annotations

import os as _os
# torch + conda-forge both ship libomp; silence the duplicate-runtime warning
# before any import can load libomp (must be set before torch first touches it).
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys as _sys
_sys.dont_write_bytecode = True

if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging
import logging.handlers
import pathlib


def _setup_logging() -> None:
    log_dir = pathlib.Path.home() / ".phi"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "phi.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    logging.getLogger("phi").info("phi log started — %s", log_file)


def _enforce_macos_app_identity(app: "QApplication") -> None:
    """macOS: register phi as a regular GUI app and set the Dock icon.

    Qt already sets NSApplicationActivationPolicyRegular, but running from the
    Terminal means there is no bundle to pull the icon from.  We also set the
    Dock icon explicitly so phi looks correct whether launched from the .app
    bundle or from a raw 'python -m phi' invocation.
    """
    import platform
    if platform.system() != "Darwin":
        return

    log = logging.getLogger("phi.main")

    # Set activation policy (Qt already does this, but be explicit)
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyRegular
        )
    except Exception as exc:
        log.debug("NSApp activation policy not set: %s", exc)

    # Set Dock icon via Qt so we never touch Apple's ImageIO / NSImage stack.
    # NSImage.initWithContentsOfFile_ on .icns files that contain PNG data
    # triggers a SIGBUS in PNGReadPlugin::InitializePluginData on macOS 26+
    # which cannot be caught by Python.  Qt's own PNG decoder (loadFromData)
    # is safe and also propagates to the Dock icon on macOS.
    try:
        from phi import icon as _phi_icon
        app.setWindowIcon(_phi_icon.load_qt())
        log.debug("Dock icon set via Qt app.setWindowIcon")
    except Exception as exc:
        log.debug("Dock icon not set: %s", exc)

    # Opt out of App Nap — macOS throttles background timers and coalesces
    # wakeups for "idle" apps.  For an audio player this means all deferred
    # drain-timer ticks fire at once the moment Cmd+Tab brings phi forward,
    # flooding the main thread right when it needs to be responsive.
    # NSActivityLatencyCritical is the flag used by AVAudioEngine / CoreAudio;
    # combined with NSActivityUserInitiated it keeps all timers at full
    # precision whether phi is in the foreground or the background.
    try:
        from Foundation import NSProcessInfo
        _NSActivityLatencyCritical = 0xFF00000000
        _NSActivityUserInitiated   = 0x00FFFFFF
        # Store at module level so the OS activity object is never garbage-collected
        # (releasing it would silently re-enable App Nap mid-session).
        global _APP_NAP_TOKEN
        _APP_NAP_TOKEN = (
            NSProcessInfo.processInfo()
            .beginActivityWithOptions_reason_(
                _NSActivityLatencyCritical | _NSActivityUserInitiated,
                "phi audio engine — low-latency timer precision required",
            )
        )
        log.debug("App Nap disabled via NSProcessInfo activity")
    except Exception as exc:
        log.debug("App Nap opt-out failed: %s", exc)


_APP_NAP_TOKEN        = None  # holds the NSProcessInfo activity while phi runs
_ACTIVATION_OBSERVER  = None  # NSNotificationCenter observer kept alive here


def _bring_window_to_front(window: "PhiMainWindow") -> None:
    """Raise and focus the main window unconditionally."""
    if window.isMinimized():
        window.showNormal()
    elif not window.isVisible():
        window.show()
    window.raise_()
    window.activateWindow()
    # Qt's raise_/activateWindow send orderFront:/makeKeyWindow to the NSWindow,
    # but when phi was spawned from Terminal the process never claimed keyboard
    # focus from the shell.  activateIgnoringOtherApps_ forces NSApp to claim
    # focus and promotes the window to the key window even in that case.
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


def _wire_cmd_tab_activation(app: "QApplication", window: "PhiMainWindow") -> None:
    """Full macOS activation wiring: Cmd+Tab, Dock click, and app reopen.

    Tracks the previous application state so we distinguish a real
    background → foreground transition (Cmd+Tab, Dock click) from an
    internal focus change (opening a dialog inside phi) and only run
    the full raise+focus sequence for genuine cross-app switches.
    """
    from PySide6.QtCore import Qt

    _prev: list[Qt.ApplicationState] = [Qt.ApplicationState.ApplicationInactive]

    def _on_state_changed(state: Qt.ApplicationState) -> None:
        prev = _prev[0]
        _prev[0] = state

        if state != Qt.ApplicationState.ApplicationActive:
            return

        # Genuine switch from background: prev was Inactive, Hidden, or Suspended
        from_background = prev in (
            Qt.ApplicationState.ApplicationInactive,
            Qt.ApplicationState.ApplicationSuspended,
            Qt.ApplicationState.ApplicationHidden,
        )
        if from_background or window.isMinimized() or not window.isVisible():
            _bring_window_to_front(window)

    app.applicationStateChanged.connect(_on_state_changed)

    # Dock icon click when app already running: QEvent::ApplicationActivate is
    # re-fired, which Qt also translates via applicationStateChanged.
    # Additionally install a NSNotificationCenter observer for
    # NSApplicationDidBecomeActiveNotification so we catch cases where the
    # Qt signal fires too early (before the NSWindow is key-ready).
    try:
        import objc
        from Foundation import NSNotificationCenter, NSObject

        class _ActivationObserver(NSObject):    # type: ignore[misc]
            @objc.python_method
            def _bring(self) -> None:
                _bring_window_to_front(window)

            def applicationDidBecomeActive_(self, _notif: object) -> None:
                self._bring()

        _obs = _ActivationObserver.alloc().init()
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            _obs,
            b"applicationDidBecomeActive:",
            "NSApplicationDidBecomeActiveNotification",
            None,
        )
        # Store at module level to prevent GC
        global _ACTIVATION_OBSERVER
        _ACTIVATION_OBSERVER = _obs
    except Exception:
        pass  # PyObjC not available or selector registration failed — Qt path only


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="python -m phi")
    parser.add_argument(
        "--bake-ascii",
        action="store_true",
        help="Pre-bake coloured ASCII art for all tracks in meta.db, then exit.",
    )
    args, _ = parser.parse_known_args()

    if args.bake_ascii:
        from phi.meta.art import ascii_bake_all
        print("Baking ASCII art cache from meta.db …")
        result = ascii_bake_all(progress=True)
        print(
            f"Done — {result['total']} unique images: "
            f"{result['baked']} baked, {result['skipped']} already cached, "
            f"{result['errors']} errors."
        )
        return

    _setup_logging()
    _log = logging.getLogger("phi.main")

    # ── PySide6 QApplication ──────────────────────────────────────────────────
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication.instance() or QApplication(_sys.argv)
    app.setApplicationName("phi")
    app.setApplicationDisplayName("φ")
    app.setOrganizationName("phi")
    app.setOrganizationDomain("phi.local")

    # macOS: phi must be a regular GUI app before any window is shown, otherwise
    # Cmd+Tab sees it as a background Python process and activation breaks.
    _enforce_macos_app_identity(app)

    # High-DPI: let Qt handle scaling automatically (PySide6 6.x default).
    # Uncomment if you need to force DPI awareness on older Qt:
    # app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)

    # ── Splash — pulse while the window constructs; no 8 s gate ───────────────
    from phi.ui.qt.splash import PhiSplashScreen
    splash = PhiSplashScreen()
    splash.show()
    app.processEvents()
    splash.start_pulse()

    # ── Build and show the main window ────────────────────────────────────────
    from phi.ui.qt.app import PhiMainWindow

    _log.info("constructing PhiMainWindow")
    window = PhiMainWindow()

    # Record launch snapshot to ~/.phi/launches.jsonl
    from phi.core.launch_log import record as _record_launch
    _record_launch(window)

    window.show()
    splash.finish(window)

    # macOS: raise + focus the window on every Cmd+Tab activation.
    # Must be wired after window.show() so the window reference is valid.
    _wire_cmd_tab_activation(app, window)

    _log.info("entering Qt event loop")
    exit_code = app.exec()
    _sys.exit(exit_code)


if __name__ == "__main__":
    main()
