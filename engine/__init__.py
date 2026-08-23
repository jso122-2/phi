"""
OctopusTracer engine package.

    from engine.gate import gate_coherence, gate_pass, COHERENCE_THRESHOLD
    from engine.bridge_factory import CAIRRNBridge, make_bridge, ARM_SHARD_MAP
    from engine.tracer_daemon import TracerDaemon, TracerSummary, Tracer
    from engine.tracer_daemon import (
        SPAWN_COLD_START, SPAWN_SHARD_DROP, SPAWN_DEGREE_ANOMALY,
        SPAWN_EMBEDDING_DRIFT, SPAWN_TICK_GATE,
    )
    from engine.vault_writer import SambaWriter, SambaResult, SambaWrite, make_samba_writer
    from engine.phi_session import PhiTracerSession, make_phi_session
    from engine.cairrn_scheduler import CAIRRNScheduler, SchedulerResult, make_cairrn_scheduler
    from engine.cairrn_dispatch import CAIRRNDispatcher, PhiAction, PhiActionKind, make_dispatcher
    from engine.hot_loader import CAIRRNHotLoader, HotLoadResult, HotLoadMetrics
    from engine.mycelial_substrate import MycelialSubstrate, MycelialTickResult
    from engine.cursor_tracer import CursorTracer, CursorSample, HoverRegion
    from engine.prefeed_shuffle import CAIRRNPrefeedShuffle, make_prefeed_shuffle
    from engine.phi_player import (
        PhiPlayer, PhiPipeline, PlayEvent,
        make_phi_player, make_phi_pipeline,
        FRAC_LOVED, FRAC_HEARD,
    )

Pipeline shortcut (wires all components from a built session in one call):

    session = make_phi_session()
    session.build()
    pipeline = make_phi_pipeline(
        session,
        hover_regions=[
            HoverRegion("play",  x=690, y=820, w=52,  h=52),
            HoverRegion("next",  x=742, y=820, w=60,  h=60),
            HoverRegion("prev",  x=630, y=820, w=60,  h=60),
        ],
    )
    pipeline.tracer.start()        # cursor daemon live
    track = pipeline.player.play_next()
    ...
    pipeline.player.report_play(0.95)
"""

from engine.gate import gate_coherence, gate_pass, is_coherent, COHERENCE_THRESHOLD
from engine.bridge_factory import CAIRRNBridge, make_bridge, ARM_SHARD_MAP, IncoherenceEvent
from engine.vault_writer import SambaWriter, SambaResult, SambaWrite, make_samba_writer
from engine.tracer_daemon import (
    TracerDaemon,
    TracerSummary,
    Tracer,
    SPAWN_COLD_START,
    SPAWN_SHARD_DROP,
    SPAWN_DEGREE_ANOMALY,
    SPAWN_EMBEDDING_DRIFT,
    SPAWN_TICK_GATE,
)
from engine.phi_session import PhiTracerSession, make_phi_session
from engine.cairrn_scheduler import CAIRRNScheduler, SchedulerResult, make_cairrn_scheduler
from engine.cairrn_dispatch import (
    CAIRRNDispatcher,
    PhiAction,
    PhiActionKind,
    DispatchResult,
    make_dispatcher,
)
from engine.hot_loader import CAIRRNHotLoader, HotLoadResult, HotLoadMetrics
from engine.mycelial_substrate import MycelialSubstrate, MycelialTickResult
from engine.cursor_tracer import CursorTracer, CursorSample, HoverRegion
from engine.phi_player import PhiPlayer, PhiPipeline, PlayEvent, make_phi_player, make_phi_pipeline, FRAC_LOVED, FRAC_HEARD

__all__ = [
    # gate
    "gate_coherence",
    "gate_pass",
    "is_coherent",
    "COHERENCE_THRESHOLD",
    # bridge
    "CAIRRNBridge",
    "make_bridge",
    "ARM_SHARD_MAP",
    "IncoherenceEvent",
    # vault writer
    "SambaWriter",
    "SambaResult",
    "SambaWrite",
    "make_samba_writer",
    # tracer daemon
    "TracerDaemon",
    "TracerSummary",
    "Tracer",
    "SPAWN_COLD_START",
    "SPAWN_SHARD_DROP",
    "SPAWN_DEGREE_ANOMALY",
    "SPAWN_EMBEDDING_DRIFT",
    "SPAWN_TICK_GATE",
    # phi session
    "PhiTracerSession",
    "make_phi_session",
    # CAIRRN scheduler
    "CAIRRNScheduler",
    "SchedulerResult",
    "make_cairrn_scheduler",
    # CAIRRN dispatcher
    "CAIRRNDispatcher",
    "PhiAction",
    "PhiActionKind",
    "DispatchResult",
    "make_dispatcher",
    # hot loader
    "CAIRRNHotLoader",
    "HotLoadResult",
    "HotLoadMetrics",
    # mycelial substrate
    "MycelialSubstrate",
    "MycelialTickResult",
    # cursor tracer
    "CursorTracer",
    "CursorSample",
    "HoverRegion",
    # phi player — playback + CAIRRN feedback loop
    "PhiPlayer",
    "PhiPipeline",
    "PlayEvent",
    "make_phi_player",
    "make_phi_pipeline",
    "FRAC_LOVED",
    "FRAC_HEARD",
]
