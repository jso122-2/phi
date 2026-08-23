# -*- coding: utf-8 -*-
"""phi.ui.qt.app — PhiMainWindow: PySide6 main window + central controller.

All mixin classes (_DispatchMixin, _TransportMixin, etc.) are reused unchanged.
Their framework dependencies are satisfied here:
  - self.after(ms, fn)      → QTimer.singleShot
  - _start_drain_threads    → QTimer-based drain pumps for _poll_queue / _dispatch_queue
  - _on_close               → hovercraft quit (closeEvent owns window death)

    Import unchanged (re-exported as PhiApp from phi.ui.qt):
        from phi.ui.qt import PhiMainWindow as PhiApp

WIRE NEEDED:
    phi/ui/_app/_keys.py → now imports from phi.ui.qt.keys (JimKeyWatcher)
    JIM_BINDING_TABLE moved to phi.ui.qt.keys (phi/watch/jim_keys.py retired)
"""
from __future__ import annotations

import logging
import os
import queue as _queue_module
import threading
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    BG, BORDER, CROSSFADE_SECS, GAPLESS, META_DB, PHI_DIR, POLL_MS, WATCH_POLL_MS,
)
from phi.core.library import Library
from phi.core.player  import PlayerEngine
from phi.core.queue   import QueueEngine
from phi.core.ranker  import TrackRanker
from phi.discovery    import DEFAULT_SCAN_DIRS, auto_discover, summarise
from phi import icon as phi_icon
from phi.audio.beat   import BeatSimulator
from phi.meta.cache   import MetaCache
from phi.meta.reader  import read_meta, scan_folder
from phi.models.bpm            import BPMModel, EmbeddingModel, EnergyModel, KeyModel, MoodModel
from phi.models.clap_model     import CLAPModel
from phi.models.gemini_clipper import GeminiClipper
from phi.models.d4_model       import D4XGBoostModel
from phi.models.meta_clipper   import MetaClipper, MetaClipperModel
from phi.models.registry       import ModelRegistry
from phi.session      import filter_existing
from phi.engine       import PhiCairrnRouter, ForestFloor
from phi.core.session_manager   import SessionManager, RestoredSession
from phi.core.meta_worker       import MetaWorker
from phi.core.poll_engine       import PollEngine
from phi.core.playback_controller import PlaybackController
from phi.engine.cairrn_router import RequestKind
from phi.core.race_watcher    import PhiRaceWatcher
import phi.core.similarity as _similarity_mod
import phi.core.ranker     as _ranker_mod
from phi.watch.watcher       import FolderWatcher
from phi.watch.lastfm        import LastFmScrobbler, build_scrobbler
from phi.watch.notify        import notify_track_change
from phi.core.playlist_store import PlaylistStore

# Qt UI components
from phi.ui.qt.now_playing import NowPlayingWidget
from phi.ui.qt.transport   import TransportWidget
from phi.ui.qt.playlist    import PlaylistWidget
from phi.ui.qt.sidebar     import SidebarWidget
from phi.ui.qt.overlay     import CommandOverlay
from phi.ui.qt.keys        import JimKeyWatcher
from phi.ui.qt.tabs        import TabbedView
from phi.ui.qt.rooms       import (
    QueueRoom,
    LibraryPage, PlaylistRoom, MixerRoom, GenreRoom,
    MLDragonPage, MLInferencePage, MLForgePage,
    ZSpinePage,
)
import phi.ui.qt.style as _qt_style
from phi.ui.qt._app_menu     import _MenuMixin
from phi.ui.qt._app_overlays import _OverlaysMixin

# Reuse all framework-agnostic mixin classes unchanged
from phi.ui._app._dispatch    import _DispatchMixin, _DRAIN_DISP_MS, _DRAIN_POLL_MS
from phi.ui._app._transport   import _TransportMixin
from phi.ui._app._queue_ops   import _QueueOpsMixin
from phi.ui._app._library_ops import _LibraryOpsMixin
from phi.ui._app._track_ui    import _TrackUIMixin
from phi.ui._app._navigation  import _NavigationMixin
from phi.ui._app._workers     import _WorkersMixin
from phi.ui._app._keys        import _KeysMixin
from phi.ui._app._window      import _WindowMixin
from phi.ui._app._session     import _SessionMixin
from phi.ui._app._octopus     import _OctopusMixin
from phi.ui._app._warmup      import _WarmupMixin


# ── _NullView — fallback for sub-views not yet in TabbedView ─────────────────

class _NullView:
    """Accepts any attribute access and any call silently."""
    def __getattr__(self, name):
        return self._noop
    @staticmethod
    def _noop(*args, **kwargs):
        pass


class _NullHyphal:
    """Stub for HyphalPanel — PollEngine calls set_energy() on it."""
    def set_energy(self, *args, **kwargs) -> None:
        pass
    def pack(self, *args, **kwargs) -> None:
        pass


class _NullInfoDrawer:
    """Stub for InfoDrawer — mixin code calls update() on it."""
    def update(self, *args, **kwargs) -> None:
        pass
    def pack(self, *args, **kwargs) -> None:
        pass
    def pack_forget(self, *args, **kwargs) -> None:
        pass


class _NullJimHelp:
    """Stub fallback for JimHelpOverlay — replaced at build time."""
    def toggle(self) -> None:
        pass


# ── PhiMainWindow ─────────────────────────────────────────────────────────────

class PhiMainWindow(
    _MenuMixin,
    _OverlaysMixin,
    _DispatchMixin,
    _TransportMixin,
    _QueueOpsMixin,
    _LibraryOpsMixin,
    _TrackUIMixin,
    _NavigationMixin,
    _WorkersMixin,
    _KeysMixin,
    _WindowMixin,
    _SessionMixin,
    _OctopusMixin,
    _WarmupMixin,
    QMainWindow,
):
    """
    Qt replacement for PhiApp(tk.Tk).

    All business logic lives in the unchanged mixin classes.  This class
    provides the Qt window surface and overrides the framework-specific hooks.
    """

    _mini:         Optional[Any]
    _settings_dlg: Optional[Any]
    _wake_disp_sig = Signal()
    _wake_poll_sig = Signal()

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        self.setWindowTitle("φ")
        self.resize(760, 720)

        # ── Thread-safe dispatch queues ───────────────────────────────────────
        self._dispatch_queue: _queue_module.Queue = _queue_module.Queue()
        self._poll_queue:     _queue_module.Queue = _queue_module.Queue()
        self._drain_active:   bool                = False
        self._closing:        bool                = False
        self._disp_timer = None
        self._poll_timer = None
        self._wake_disp_sig.connect(self._kick_disp_timer)
        self._wake_poll_sig.connect(self._kick_poll_timer)
        self._log = logging.getLogger("phi.app")

        # ── persistent metadata cache ─────────────────────────────────────────
        PHI_DIR.mkdir(parents=True, exist_ok=True)
        self.meta_cache = MetaCache(META_DB)

        # ── engines ───────────────────────────────────────────────────────────
        self.library  = Library()
        self.queue    = QueueEngine()
        self.player   = PlayerEngine()
        self.watcher  = FolderWatcher()
        self._beat    = BeatSimulator()

        # Route AVPlayer main-thread dispatch through Qt's poll_queue so
        # _play_when_ready callbacks land on the Qt event loop reliably.
        # (NSRunLoop.performBlock_ is not guaranteed to fire while PySide6 owns
        # the event loop, which caused silent playback failures on track select.)
        from phi.core.player import register_qt_dispatch
        def _player_dispatch(fn) -> None:
            self._poll_queue.put(fn)
            self._wake_drain("poll")
        register_qt_dispatch(_player_dispatch)

        # ── race watchdog ─────────────────────────────────────────────────────
        self.race_watcher = PhiRaceWatcher(
            crossfade_secs=CROSSFADE_SECS,
            poll_ms=POLL_MS,
        )

        # ── playlist store ────────────────────────────────────────────────────
        self.playlist_store = PlaylistStore(META_DB)

        # ── sleep timer ───────────────────────────────────────────────────────
        from phi.ui.qt.sleep_timer import SleepTimer
        self.sleep_timer = SleepTimer(
            schedule  = self._sched,
            on_expire = self.on_play_pause,
            on_tick   = self._on_sleep_tick,
        )

        # ── Last.fm scrobbler ─────────────────────────────────────────────────
        self._scrobbler: LastFmScrobbler | None = build_scrobbler(self._sched)
        self._scrobble_ts: int = 0

        # ── model registry ────────────────────────────────────────────────────
        self.models = ModelRegistry()
        self.models.register(BPMModel())
        self.models.register(KeyModel())
        self.models.register(EnergyModel())
        self.models.register(MoodModel())
        self.models.register(CLAPModel())
        self.models.register(EmbeddingModel())
        # GeminiClipper is a query/clip tool, not a batch PhiModel —
        # instantiate it with its required dependencies and store separately.
        from phi.models.clap_proj import CLAPProjection
        from phi.models._metadata_encoder import MetadataEncoder
        self.clipper = GeminiClipper(
            proj=CLAPProjection.load_default(),
            encoder=MetadataEncoder(),
        )
        _mc_ckpt = PHI_DIR / "meta_clipper.joblib"
        if _mc_ckpt.exists():
            try:
                self.models.register(MetaClipperModel(MetaClipper.load(_mc_ckpt)))
            except Exception as _e:
                self._log.warning("meta_clipper checkpoint load failed: %s", _e)
        _d4 = D4XGBoostModel()
        _d4_ckpt = PHI_DIR / "d4_xgb.joblib"
        if _d4_ckpt.exists():
            try:
                _d4 = D4XGBoostModel.load(_d4_ckpt)
            except Exception as _e:
                self._log.warning("d4_xgb checkpoint load failed: %s", _e)
        self.models.register(_d4)

        # ── smart playlists ───────────────────────────────────────────────────
        from phi.core.smart_playlist import SmartPlaylist
        self.smart_playlists: list[SmartPlaylist] = []

        # ── metadata enrichment ───────────────────────────────────────────────
        from phi.config import enrich_config
        from phi.meta.review_queue import ReviewQueue
        from phi.watch.enrich_daemon import EnrichDaemon

        self.review_queue  = ReviewQueue()
        self.enrich_config = enrich_config()

        _api_key = self.enrich_config.get("acoustid_api_key", "")
        _pause_during_pb = bool(self.enrich_config.get("pause_during_playback", True))
        _is_playing_fn = (
            (lambda: self.player.is_busy() and not self.player.paused)
            if _pause_during_pb
            else (lambda: False)
        )
        self.enrich_daemon = EnrichDaemon(
            library=self.library,
            review_queue=self.review_queue,
            api_key=_api_key,
            is_playing=_is_playing_fn,
            on_progress=self._on_enrich_progress,
            schedule=self.dispatch,
            mb_contact=self.enrich_config.get("mb_user_agent", "phi@local"),
            threshold=float(self.enrich_config.get("confidence_threshold", 0.70)),
            write_back=bool(self.enrich_config.get("write_back_enabled", True)),
            inter_track_s=float(self.enrich_config.get("inter_track_seconds", 1.0)),
            enrich_online=bool(self.enrich_config.get("enrich_online", False)),
            meta_cache=self.meta_cache,
            on_batch_complete=self._init_octopus_bg,
        )

        # ── ranker ────────────────────────────────────────────────────────────
        self.ranker: TrackRanker   = TrackRanker()
        self.ranker_enabled: bool  = False
        self.picker_enabled: bool  = False

        # ── CAIRRN floor ──────────────────────────────────────────────────────
        self.floor = ForestFloor(ipc_enabled=True)
        self.floor.load_state()

        import phi.core.queue as _queue_mod_floor
        import phi.models.clap_model as _clap_mod
        _ranker_mod.bind_floor(self.floor)
        _similarity_mod.bind_floor(self.floor)
        _queue_mod_floor.bind_floor(self.floor)
        _clap_mod.bind_floor(self.floor)
        if self.enrich_daemon is not None:
            self.enrich_daemon.bind_floor(self.floor)

        # ── CAIRRN dispatcher ─────────────────────────────────────────────────
        from sims.harmonic import HarmonicIndex as _HarmonicIndex
        from engine.cairrn_dispatch import make_dispatcher as _make_dispatcher
        self._cairrn_index = _HarmonicIndex(n_harmonics=8, coupling=0.15)
        self.cairrn_dispatcher = _make_dispatcher(
            harmonic_index=self._cairrn_index,
            forest_floor=self.floor,
            tau=10.0,
        )

        # Track wall-clock time of last active state for on_resume() credit.
        # CairnTick fires every 10 × POLL_MS = 1 s — use that as tick_interval.
        self._last_active_at: float = _time.monotonic()
        self._cairrn_tick_interval_s: float = POLL_MS / 1000.0 * 10
        QApplication.instance().applicationStateChanged.connect(
            self._on_app_state_changed
        )

        # ── CurveDaemon — dragon-curve background ML (A: fold inject, B: arc, C: log) ──
        from phi.engine.curve_daemon import CurveDaemon
        self.curve_daemon = CurveDaemon(
            harmonic_index = self._cairrn_index,
            meta_cache     = self.meta_cache,
            library        = self.library,
        )
        # Wire arc pre-queue callback (arc engine calls this after each track change)
        self.curve_daemon._on_suggest_next = self.on_play_next_path

        # ── media key handler ─────────────────────────────────────────────────
        from phi.audio.media_keys import MediaKeyHandler
        self.media_keys = MediaKeyHandler(
            schedule      = self._sched,
            on_play_pause = self.on_play_pause,
            on_next       = self.on_next,
            on_prev       = self.on_prev,
            on_vol_up     = lambda: self._vol_step(+0.05),
            on_vol_down   = lambda: self._vol_step(-0.05),
            on_mute       = self.on_toggle_mute,
        )
        self._np_poll_tick: int = 0
        self._cairrn_tick:  int = 0

        # ── ui-level state ────────────────────────────────────────────────────
        self.duration: float        = 0.0
        self._track_start_pos: float = 0.0

        # ── build Qt UI ───────────────────────────────────────────────────────
        _qt_style.apply(QApplication.instance())
        self.setWindowIcon(phi_icon.load_qt())

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (starts hidden; ⌘B toggles it)
        self.sidebar = SidebarWidget(ctrl=self, parent=central)
        main_layout.addWidget(self.sidebar)

        # Page area — QStackedWidget holds all pages
        self._page_slot = QStackedWidget(central)
        main_layout.addWidget(self._page_slot, stretch=1)

        # ── playing page ──────────────────────────────────────────────────────
        playing_page = QWidget()
        playing_layout = QVBoxLayout(playing_page)
        playing_layout.setContentsMargins(0, 0, 0, 0)
        playing_layout.setSpacing(0)

        self.now_playing = NowPlayingWidget(schedule=self._sched, parent=playing_page)
        playing_layout.addWidget(self.now_playing, stretch=1)

        self.transport = TransportWidget(ctrl=self, parent=playing_page)
        playing_layout.addWidget(self.transport)

        # Null stubs for Tk-only panels consumed by PollEngine / mixin code
        self.wave        = None
        self.hyphal      = _NullHyphal()
        self.info_drawer = _NullInfoDrawer()

        # TabbedView lives on the library page; create without a parent so it
        # can be reparented into LibraryPage via embed_tabs() below.
        _tabs_view = TabbedView(ctrl=self, parent=None)

        self.tabs           = _tabs_view
        self.playlist_panel = _tabs_view.tracks_view

        # ── register pages ────────────────────────────────────────────────────
        self._queue_page    = QueueRoom(parent=self._page_slot,    ctrl=self)
        self._library_page  = LibraryPage(parent=self._page_slot,  ctrl=self)
        self._library_page.embed_tabs(_tabs_view)
        self._playlist_page = PlaylistRoom(parent=self._page_slot, ctrl=self)
        self._mixer_page    = MixerRoom(parent=self._page_slot,    ctrl=self)
        self._genre_page    = GenreRoom(parent=self._page_slot,    ctrl=self)

        _PAGE_NAMES = ["playing", "queue", "library", "playlist", "genre", "mixer"]
        self._page_frames: dict[str, QWidget] = {
            "playing":  playing_page,
            "queue":    self._queue_page,
            "library":  self._library_page,
            "playlist": self._playlist_page,
            "genre":    self._genre_page,
            "mixer":    self._mixer_page,
        }
        self._page_names = _PAGE_NAMES
        self._page_idx   = 0
        self._in_rooms   = False

        for page in [
            playing_page,
            self._queue_page,
            self._library_page,
            self._playlist_page,
            self._genre_page,
            self._mixer_page,
        ]:
            self._page_slot.addWidget(page)
        self._page_slot.setCurrentWidget(playing_page)

        # ── ML pages ─────────────────────────────────────────────────────────
        self._ml_dragon    = MLDragonPage(parent=self._page_slot,    ctrl=self)
        self._ml_inference = MLInferencePage(parent=self._page_slot,  ctrl=self)
        self._ml_forge     = MLForgePage(parent=self._page_slot,     ctrl=self)

        _ML_PAGE_NAMES = ["ml_dragon", "ml_inference", "ml_forge"]
        self._ml_page_frames: dict[str, QWidget] = {
            "ml_dragon":    self._ml_dragon,
            "ml_inference": self._ml_inference,
            "ml_forge":     self._ml_forge,
        }
        self._ml_page_names = _ML_PAGE_NAMES
        self._ml_page_idx   = 0
        self._in_ml_table   = False

        for ml_page in [self._ml_dragon, self._ml_inference, self._ml_forge]:
            self._page_slot.addWidget(ml_page)

        # ── Z spine (content to be added in a future session) ─────────────────
        self._z_page_0 = ZSpinePage(parent=self._page_slot, ctrl=self)

        _Z_PAGE_NAMES = ["z_0"]
        self._z_page_frames: dict[str, QWidget] = {
            "z_0": self._z_page_0,
        }
        self._z_page_names = _Z_PAGE_NAMES
        self._z_page_idx   = 0
        self._in_z_spine   = False

        self._page_slot.addWidget(self._z_page_0)

        # ── overlays ──────────────────────────────────────────────────────────
        self._overlay  = CommandOverlay(parent=self, ctrl=self)
        from phi.ui.qt.jim_help import JimHelpOverlay
        self._jim_help = JimHelpOverlay(parent=self)

        # ── sub-controllers ───────────────────────────────────────────────────
        self.session_mgr = SessionManager()

        self.meta_worker = MetaWorker(
            library           = self.library,
            meta_cache        = self.meta_cache,
            models            = self.models,
            schedule          = self.dispatch,
            on_meta_ready     = self._on_meta_ready,
            on_refresh        = self._refresh_playlist,
            on_flush          = self._flush_annotations,
            floor             = self.floor,
            get_duration      = lambda: self.duration,
            set_duration      = lambda v: setattr(self, "duration", v),
            on_duration_ready = lambda dur: self.transport.set_end(dur),
        )

        self.playback = PlaybackController(
            player               = self.player,
            queue                = self.queue,
            library              = self.library,
            transport            = self.transport,
            race_watcher         = self.race_watcher,
            ranker               = self.ranker,
            beat                 = self._beat,
            floor                = self.floor,
            schedule             = self._sched,
            flash                = self._flash,
            meta_worker          = self.meta_worker,
            on_apply_track_to_ui = self._apply_track_to_ui,
            on_preload_art       = self._preload_art_for_path,
            on_open_picker       = self._open_picker,
            on_play_path         = self.on_play_path,
            on_refresh_playlist  = self._refresh_playlist,
            get_ranker_enabled   = lambda: self.ranker_enabled,
            get_picker_enabled   = lambda: self.picker_enabled,
            get_duration         = lambda: self.duration,
            set_duration         = lambda v: setattr(self, "duration", v),
            scrobbler            = self._scrobbler,
            on_skip              = lambda p, pos: self.curve_daemon.on_skip(p, pos),
        )

        self.poll_engine = PollEngine(
            player          = self.player,
            queue           = self.queue,
            transport       = self.transport,
            race_watcher    = self.race_watcher,
            beat            = self._beat,
            hyphal          = self.hyphal,
            floor           = self.floor,
            media_keys      = self.media_keys,
            schedule        = self.after,
            on_advance      = self.playback.advance,
            peek_next_path  = self.playback.peek_next_path,
            get_duration    = lambda: self.duration,
            set_duration    = lambda v: setattr(self, "duration", v),
            on_crossfade_handoff = self.playback.handoff_after_crossfade,
            sync_rooms      = self._poll_rooms_transport,
            get_mini        = lambda: getattr(self, "_mini", None),
            wave            = self.wave,
            dispatcher      = self.cairrn_dispatcher,
        )

        self._picker:         Optional[Any] = None
        self._octopus_thread: Optional[threading.Thread] = None

        self._bind_keys()
        self._build_macos_menu()
        self._restore_session()
        self.floor.root_pulse("playing")

        self._sched(0, self._start_warmup)
        threading.Thread(
            target=self._warm_floor_bg, daemon=True, name="phi-floor-warm"
        ).start()

        if self.library.size == 0:
            threading.Thread(target=self._auto_discover, daemon=True).start()

        from phi.watch.librosa_worker import LibrosaWorker
        self.librosa_worker = LibrosaWorker(
            library=self.library,
            is_playing=_is_playing_fn,
            on_progress=self._on_librosa_progress,
            schedule=self.dispatch,
            inter_track_s=float(self.enrich_config.get("librosa_inter_track_seconds", 2.0)),
        )

        from phi.meta.art_spider import get_art_spider
        self.art_spider = get_art_spider(self.library, self.meta_cache)
        self._sched(8_000, self.art_spider.start)

        if self.enrich_daemon:
            self._sched(5_000, self.enrich_daemon.start)

        self._sched(20_000, self.librosa_worker.start)
        self._sched(60_000, self._init_octopus_bg)

        self.media_keys.start()
        self.poll_engine.start()
        self._watch_poll()
        self._start_drain_threads()

        if self.library.size == 0:
            self._sched(600, self._show_onboarding)

    def _warm_floor_bg(self) -> None:
        """Replay recent plays onto the floor off the UI thread."""
        try:
            self.floor.warm_from_history(self.library)
        except Exception:
            pass

    # ── Qt framework hooks ────────────────────────────────────────────────────

    def after(self, delay_ms: int, fn: Callable) -> str:
        """Schedule *fn* on the Qt main thread after *delay_ms* milliseconds.

        Returns an empty string for compatibility with code that captures the
        return value (the old Tk after-id pattern); callers never use it.
        Pending shots become no-ops once quit has started.
        """
        if self._closing:
            return ""

        def _guarded() -> None:
            if self._closing:
                return
            fn()

        QTimer.singleShot(delay_ms, _guarded)
        return ""

    def destroy(self) -> None:
        """No-op. Window death is owned by closeEvent — do not call close() here."""
        return

    def focus(self) -> None:
        """Called from key mixin on Escape / deselect."""
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._on_close()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if hasattr(self, "jim") and self.jim.handle_key(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if hasattr(self, "jim") and self.jim.handle_key_release(event):
            event.accept()
            return
        super().keyReleaseEvent(event)

    # ── Override _start_drain_threads to use QTimer ───────────────────────────

    def _start_drain_threads(self) -> None:
        """Drain pumps that idle-stop when their queue is empty."""
        self._drain_active = True

        def _make_pump(q: _queue_module.Queue, interval_ms: int, precise: bool):
            timer = QTimer(self)
            timer.setTimerType(
                Qt.TimerType.PreciseTimer if precise else Qt.TimerType.CoarseTimer
            )
            timer.setInterval(interval_ms)

            def _tick():
                if not self._drain_active or self._closing:
                    timer.stop()
                    return
                drained = 0
                while drained < 64:
                    try:
                        fn = q.get_nowait()
                    except _queue_module.Empty:
                        break
                    try:
                        fn()
                    except Exception:
                        pass
                    drained += 1
                if drained == 0:
                    timer.stop()

            timer.timeout.connect(_tick)
            timer.start()
            return timer

        self._disp_timer = _make_pump(self._dispatch_queue, _DRAIN_DISP_MS, precise=False)
        self._poll_timer = _make_pump(self._poll_queue,     _DRAIN_POLL_MS, precise=True)

    def _wake_drain(self, which: str) -> None:
        if not self._drain_active or self._closing:
            return
        if which == "disp":
            self._wake_disp_sig.emit()
        else:
            self._wake_poll_sig.emit()

    def _kick_disp_timer(self) -> None:
        if self._drain_active and self._disp_timer is not None and not self._disp_timer.isActive():
            self._disp_timer.start()

    def _kick_poll_timer(self) -> None:
        if self._drain_active and self._poll_timer is not None and not self._poll_timer.isActive():
            self._poll_timer.start()

    # ── App-lifecycle → CAIRRN resume ─────────────────────────────────────────

    def _on_app_state_changed(self, state: Qt.ApplicationState) -> None:
        """Credit idle time back to the CAIRRN dispatcher on app activation.

        macOS App Nap and Cmd+Tab both send ApplicationInactive → ApplicationActive
        transitions.  We record the wall-clock time when the app goes inactive and
        compute idle_s on re-activation.  That idle time is converted to equivalent
        dispatcher step count so the coherence gate rebuilds as if ticking had
        continued normally during the background period.

        Also called with idle_s=0 on inactive to reset _last_active_at — this
        ensures back-to-back activations accumulate only the true gap.
        """
        now = _time.monotonic()
        if state == Qt.ApplicationState.ApplicationActive:
            idle_s = max(0.0, now - self._last_active_at)
            if idle_s >= 1.0:
                self.cairrn_dispatcher.on_resume(
                    idle_s=idle_s,
                    tick_interval_s=self._cairrn_tick_interval_s,
                )
            self._last_active_at = now
        elif state in (
            Qt.ApplicationState.ApplicationInactive,
            Qt.ApplicationState.ApplicationSuspended,
            Qt.ApplicationState.ApplicationHidden,
        ):
            self._last_active_at = now

    # ── Page routing (Qt-specific) ────────────────────────────────────────────

    def go_to_page(self, name: str) -> None:
        """Switch the visible page in the QStackedWidget."""
        page = self._page_frames.get(name)
        if page and page in [
            self._page_slot.widget(i)
            for i in range(self._page_slot.count())
        ]:
            self._page_slot.setCurrentWidget(page)
            self._page_idx = list(self._page_frames.keys()).index(name)
            # Reset soot-ash state — user is navigating; inherited tau-stretch
            # from background ring activity must not delay the next transport action.
            try:
                self.cairrn_dispatcher.on_resume(0.0)
            except Exception:
                pass

    def toggle_page(self, name: str) -> None:
        """Toggle between the named page and 'playing'."""
        current = self._page_slot.currentWidget()
        target  = self._page_frames.get(name)
        if current is target:
            self.go_to_page("playing")
        else:
            self.go_to_page(name)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── ML table navigation (QStackedWidget-native) ───────────────────────────

    def _enter_ml_table(self) -> None:
        old = self._page_names[self._page_idx]
        old_widget = self._page_frames.get(old)
        if old_widget:
            self._page_slot.setCurrentWidget(old_widget)
        self._in_ml_table = True
        self._in_rooms    = True
        name  = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def _leave_ml_table(self) -> None:
        name  = self._ml_page_names[self._ml_page_idx]
        self._in_ml_table = False
        self._in_rooms    = False
        self._page_idx    = 0
        self._page_slot.setCurrentWidget(self._page_frames["playing"])
        self.setWindowTitle("φ")
        self.floor.root_pulse("playing")

    def ml_next_page(self) -> None:
        if not self._in_ml_table:
            return
        self._ml_page_idx = (self._ml_page_idx + 1) % len(self._ml_page_names)
        name  = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def ml_prev_page(self) -> None:
        if not self._in_ml_table:
            return
        self._ml_page_idx = (self._ml_page_idx - 1) % len(self._ml_page_names)
        name  = self._ml_page_names[self._ml_page_idx]
        frame = self._ml_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  ML / {name.replace('ml_', '').title()}")
        self.floor.root_pulse(name)

    def toggle_ml_table(self) -> None:
        if self._in_ml_table:
            self._leave_ml_table()
        else:
            self._enter_ml_table()

    # ── Z-spine navigation (QStackedWidget-native) ────────────────────────────

    def toggle_z_spine(self) -> None:
        if self._in_z_spine:
            self._leave_z_spine()
        else:
            self._enter_z_spine()

    def _enter_z_spine(self) -> None:
        if self._in_ml_table:
            self._leave_ml_table()
        self._in_z_spine = True
        self._in_rooms   = True
        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)
        self._cairrn_route_key("toggle_z_spine", "agent-context", 0.60)

    def _leave_z_spine(self) -> None:
        self._in_z_spine = False
        self._in_rooms   = False
        self._page_idx   = 0
        self._page_slot.setCurrentWidget(self._page_frames["playing"])
        self.setWindowTitle("φ")
        self.floor.root_pulse("playing")

    def z_next_page(self) -> None:
        if not self._in_z_spine:
            return
        self._z_page_idx = (self._z_page_idx + 1) % len(self._z_page_names)
        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)

    def z_prev_page(self) -> None:
        if not self._in_z_spine:
            return
        self._z_page_idx = (self._z_page_idx - 1) % len(self._z_page_names)
        name  = self._z_page_names[self._z_page_idx]
        frame = self._z_page_frames[name]
        self._page_slot.setCurrentWidget(frame)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self.setWindowTitle(f"φ  ·  Z / {name.replace('z_', '').title()}")
        self.floor.root_pulse(name)

    def toggle_rooms(self) -> None:
        """Toggle between playing page and the last-active room."""
        if self._in_z_spine:
            self._leave_z_spine()
            return
        if self._in_rooms:
            self.go_to_page("playing")
            self._in_rooms = False
        else:
            name = self._page_names[1] if len(self._page_names) > 1 else "playing"
            self.go_to_page(name)
            self._in_rooms = True


# ── Public alias (keeps phi/__main__.py import unchanged) ─────────────────────
PhiApp = PhiMainWindow
