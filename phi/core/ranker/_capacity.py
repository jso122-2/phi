"""F_ADAPTIVE_CAPACITY and F_CC wraps. Pure floats, no floor I/O."""
from __future__ import annotations

from workers.cairrn.formulas import f_cc_energy_budget
from workers.cairrn.mycelial import f_adaptive_capacity

from ._constants import AC_WEIGHT_N, AC_WEIGHT_S, AC_WEIGHT_T, CC_CEILING


def adaptive_capacity(
    nutrient_headroom: float,
    shi_margin: float,
    tracer_slack: float,
    tag_set_a: float = 0.0,
) -> float:
    """Session headroom AC = w_N·N + w_S·M_SHI + w_T·S_T + A."""
    return f_adaptive_capacity(
        AC_WEIGHT_N,
        nutrient_headroom,
        AC_WEIGHT_S,
        shi_margin,
        AC_WEIGHT_T,
        tracer_slack,
        tag_set_a=tag_set_a,
    )


def cc_budget_score(
    ac_headroom: float,
    pressure: float,
    tracer_consensus: float,
) -> float:
    """Spendable Cc. A_used = c − min(c, AC) so high headroom raises Cc."""
    a_used = max(0.0, CC_CEILING - min(CC_CEILING, ac_headroom))
    return f_cc_energy_budget(CC_CEILING, a_used, pressure, tracer_consensus)
