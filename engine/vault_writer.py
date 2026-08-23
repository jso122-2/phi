"""
SambaWriter — arm score → vault mutation layer.

Final stage of the OctopusTracer pipeline (ARCHITECTURE LOCKED — pow.md):

    8 MLP HEADS (arms) → SUCKER LAYER → Samba MCP → vault writes

Arm → vault action mapping:
    PRUNE     → prune-flag node  (mark high-score nodes for human review)
    GRAFT     → graft node       (structural join between complement neighbours)
    CLUSTER   → cluster node     (wikilinks between high-score neighbour pairs)
    RANK      → rank node        (priority metadata update)
    TAG       → tag node         (content-derived tag annotation)
    RESURFACE → resurface node   (orphan → hub wikilink reinstated)
    MERGE     → merge-candidate  (annotation on both merge targets)
    SPROUT    → sprout node      (new node — structural gap in graph)

Coherence gate (engine/gate.py):
    coherence < W(1) ≈ 0.5671  →  dry-run; decisions computed but NOT written to disk
    coherence ≥ W(1) ≈ 0.5671  →  live writes to  sessions/samba/<timestamp>-<arm>-<slug>.md

Each arm fires independently when its mean score exceeds `arm_threshold`.
Arm nodes are written to:  <vault_root>/sessions/samba/

All writes are append-only — SambaWriter never overwrites existing nodes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.gate import COHERENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMBA_SUBDIR = "sessions/samba"
_ARM_THRESHOLD_DEFAULT = 0.0   # any non-zero mean score triggers the arm
                                # (arm outputs are small; threshold is deliberate)

# Arm → hub link (for footer wikilinks)
_ARM_HUB: dict[str, str] = {
    "PRUNE":     "HOME",
    "GRAFT":     "MATH",
    "CLUSTER":   "MATH",
    "RANK":      "CODE",
    "TAG":       "CODE",
    "RESURFACE": "COMMANDS",
    "MERGE":     "agent-context",
    "SPROUT":    "agent-context",
}

# Arm → human description
_ARM_DESC: dict[str, str] = {
    "PRUNE":     "structural pruning candidate — high complement-graph centrality",
    "GRAFT":     "graft target — complement edge warrants structural join",
    "CLUSTER":   "cluster candidate — dense complement neighbourhood",
    "RANK":      "rank elevation — high tangent flow through this node",
    "TAG":       "tag candidate — embedding drift signals content shift",
    "RESURFACE": "resurface candidate — orphaned but high angular proximity to hub",
    "MERGE":     "merge candidate — near-duplicate in embedding space",
    "SPROUT":    "sprout target — structural gap in graph neighbourhood",
}


# ---------------------------------------------------------------------------
# Write result
# ---------------------------------------------------------------------------

@dataclass
class SambaWrite:
    """Record of one arm's vault write decision."""
    arm: str
    score: float
    coherence: float
    dry_run: bool
    path: Optional[Path] = None     # None when dry_run=True
    content: str = ""


@dataclass
class SambaResult:
    """Aggregated result from one SambaWriter.process() call."""
    tick: int
    coherence: float
    coherent: bool
    writes: list[SambaWrite] = field(default_factory=list)
    n_written: int = 0
    n_suppressed: int = 0

    def summary(self) -> dict:
        return {
            "tick":        self.tick,
            "coherence":   round(self.coherence, 4),
            "coherent":    self.coherent,
            "n_written":   self.n_written,
            "n_suppressed": self.n_suppressed,
            "arms_fired":  [w.arm for w in self.writes],
        }


# ---------------------------------------------------------------------------
# SambaWriter
# ---------------------------------------------------------------------------

class SambaWriter:
    """
    Translates TracerDaemon arm scores into vault file mutations.

    Parameters
    ----------
    vault_root      : path to the Obsidian vault root (Spotify-rip/)
    arm_threshold   : minimum mean arm score to trigger a write (default 0.0)
    coherence_threshold : below this → dry-run (default W(1) ≈ 0.5671 from gate)
    """

    def __init__(
        self,
        vault_root: Path,
        arm_threshold: float = _ARM_THRESHOLD_DEFAULT,
        coherence_threshold: float = COHERENCE_THRESHOLD,
    ) -> None:
        self.vault_root = Path(vault_root)
        self.arm_threshold = arm_threshold
        self.coherence_threshold = coherence_threshold
        self._tick: int = 0

        samba_dir = self.vault_root / SAMBA_SUBDIR
        samba_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(
        self,
        arm_means: dict[str, float],
        coherence: float,
    ) -> SambaResult:
        """
        Evaluate each arm's mean score and write vault nodes.

        Parameters
        ----------
        arm_means   : dict of arm_name → mean score over all N nodes
        coherence   : current coherence from gate_coherence()

        Returns
        -------
        SambaResult
        """
        is_coherent = coherence >= self.coherence_threshold
        ts = datetime.now(timezone.utc)

        result = SambaResult(
            tick=self._tick,
            coherence=coherence,
            coherent=is_coherent,
        )

        for arm, score in arm_means.items():
            if score <= self.arm_threshold:
                continue

            content = self._render_arm_node(arm, score, coherence, ts)

            if not is_coherent:
                # Dry run — decision computed but not written
                w = SambaWrite(
                    arm=arm, score=score, coherence=coherence,
                    dry_run=True, content=content,
                )
                result.n_suppressed += 1
            else:
                # Live write
                path = self._write(arm, score, ts, content)
                w = SambaWrite(
                    arm=arm, score=score, coherence=coherence,
                    dry_run=False, path=path, content=content,
                )
                result.n_written += 1

            result.writes.append(w)

        self._tick += 1
        return result

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_arm_node(
        self,
        arm: str,
        score: float,
        coherence: float,
        ts: datetime,
    ) -> str:
        hub = _ARM_HUB.get(arm, "HOME")
        desc = _ARM_DESC.get(arm, arm.lower())
        ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")

        return (
            f"# Samba: {arm.capitalize()} signal\n\n"
            f"#samba #{arm.lower()} #tracer-output\n\n"
            f"**Arm:** `{arm}`  \n"
            f"**Score:** {score:.6g}  \n"
            f"**Coherence:** {coherence:.4f}  \n"
            f"**Tick:** {self._tick}  \n"
            f"**Timestamp:** {ts_str}  \n\n"
            f"---\n\n"
            f"## Signal\n\n"
            f"{desc.capitalize()}.\n\n"
            f"OctopusTracer `{arm}` arm fired above threshold.  \n"
            f"Arm authority: {'**LIVE** — writes applied' if coherence >= self.coherence_threshold else '**SUPPRESSED** — coherence below gate (dry-run)'}.\n\n"
            f"---\n\n"
            f"→ [[{hub}]]  \n"
            f"→ [[sessions]]  \n"
            f"→ [[live-state]]  \n\n"
            f"*Written by `engine/vault_writer.py` — Samba MCP arm output.*\n"
        )

    def _write(self, arm: str, score: float, ts: datetime, content: str) -> Path:
        samba_dir = self.vault_root / SAMBA_SUBDIR
        slug = _slug(arm)
        filename = f"{ts.strftime('%Y-%m-%d-%H%M%S')}-{slug}.md"
        path = samba_dir / filename
        # Append microseconds to avoid collisions when multiple arms fire on same tick
        if path.exists():
            filename = f"{ts.strftime('%Y-%m-%d-%H%M%S')}-{ts.microsecond}-{slug}.md"
            path = samba_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------

    @property
    def samba_dir(self) -> Path:
        return self.vault_root / SAMBA_SUBDIR

    def __repr__(self) -> str:
        return (
            f"<SambaWriter vault={self.vault_root.name!r} "
            f"tick={self._tick} threshold={self.arm_threshold}>"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str, maxlen: int = 20) -> str:
    return _SLUG_RE.sub("-", text.lower()[:maxlen]).strip("-")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_samba_writer(
    vault_root: Optional[Path] = None,
    arm_threshold: float = _ARM_THRESHOLD_DEFAULT,
) -> SambaWriter:
    """
    Construct a SambaWriter.  Defaults to the project vault root if not given.
    """
    if vault_root is None:
        from graph.node import _PACKAGE_ROOT
        vault_root = _PACKAGE_ROOT
    return SambaWriter(vault_root=vault_root, arm_threshold=arm_threshold)
