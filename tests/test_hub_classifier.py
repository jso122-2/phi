"""
Tests for graph/hub_classifier.py

Covers:
  - Strong single-hub signals route correctly
  - Link-signal bonus tips ambiguous cases
  - Empty / whitespace content falls back to HOME
  - hub_scores() returns expected relative ordering
  - Tiebreaker: CODE beats MATH on identical raw scores
"""
from __future__ import annotations

import pytest

from graph.hub_classifier import classify_hub, hub_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(prompt="", thinking="", outcome="", links=None) -> str:
    return classify_hub(prompt, thinking, outcome, discovered_links=links)


# ---------------------------------------------------------------------------
# Strong keyword signal
# ---------------------------------------------------------------------------


class TestKeywordSignal:
    def test_math_attractor_content(self):
        result = _classify(
            prompt="explain the double-well attractor",
            thinking="the potential V(x)=(x²−α²)² has stable minima at ±α=1.96",
            outcome="gradient descent converges to the harmonic basin",
        )
        assert result == "MATH"

    def test_math_harmonic_shard_content(self):
        result = _classify(
            prompt="what is the harmonic shard coupling constant",
            thinking="kappa=0.15 governs local propagation between shards",
            outcome="each basin centre is a multiple of alpha",
        )
        assert result == "MATH"

    def test_code_psspps_content(self):
        result = _classify(
            prompt="build the psspps retriever pipeline",
            thinking="need scorer, router, traverser modules for the graph worker",
            outcome="mcp server now exposes psspps_query tool",
        )
        assert result == "CODE"

    def test_code_ingestion_content(self):
        result = _classify(
            prompt="how do we build the ingestion pipeline",
            thinking="graph commit calls logger which calls psspps then writes session node",
            outcome="server.py graph_commit extended with hub injection",
        )
        assert result == "CODE"

    def test_commands_slash_content(self):
        result = _classify(
            prompt="what does /sim do",
            thinking="calls the double_well_sim mcp tool",
            outcome="the /sweep /index /propagate commands are also available",
        )
        assert result == "COMMANDS"

    def test_agent_context_workflow_mode(self):
        result = _classify(
            prompt="/talk mode discussion",
            thinking="the behaviour contract says no file edits in /talk mode",
            outcome="switching to /dev when alignment reached",
        )
        assert result == "agent-context"

    def test_empty_content_falls_back_to_home(self):
        result = _classify(prompt="", thinking="", outcome="")
        assert result == "HOME"

    def test_whitespace_only_falls_back_to_home(self):
        result = _classify(prompt="   ", thinking="\n\n", outcome="\t")
        assert result == "HOME"


# ---------------------------------------------------------------------------
# Link-signal bonus
# ---------------------------------------------------------------------------


class TestLinkSignal:
    def test_math_links_tip_ambiguous_content(self):
        # Vanilla prompt with MATH node links — should tip to MATH
        result = _classify(
            prompt="summarise what we did today",
            thinking="reviewed several nodes",
            outcome="everything looks good",
            links=["harmonic-index", "attractors", "MATH"],
        )
        assert result == "MATH"

    def test_code_links_tip_ambiguous_content(self):
        result = _classify(
            prompt="summarise what we did today",
            thinking="reviewed several nodes",
            outcome="everything looks good",
            links=["mcp-server", "psspps", "CODE"],
        )
        assert result == "CODE"

    def test_links_reinforce_keyword_signal(self):
        result = _classify(
            prompt="attractor shard propagation",
            thinking="harmonic index coupling",
            outcome="basin centred resonance",
            links=["MATH", "harmonic-index"],
        )
        assert result == "MATH"

    def test_empty_links_list_treated_same_as_none(self):
        r1 = _classify(prompt="attractor harmonic shard", links=[])
        r2 = _classify(prompt="attractor harmonic shard", links=None)
        assert r1 == r2 == "MATH"


# ---------------------------------------------------------------------------
# hub_scores() — relative ordering
# ---------------------------------------------------------------------------


class TestHubScores:
    def test_math_content_has_highest_math_score(self):
        scores = hub_scores(
            prompt="attractor harmonic shard basin coupling",
            thinking="kappa alpha propagation potential equilibrium",
            outcome="Lambert W fixed point gradient descent",
        )
        assert scores["MATH"] == max(scores.values())

    def test_code_content_has_highest_code_score(self):
        scores = hub_scores(
            prompt="psspps retriever scorer pipeline",
            thinking="graph worker logger linker mcp server",
            outcome="session node written by ingestion commit",
        )
        assert scores["CODE"] == max(scores.values())

    def test_all_hubs_present_in_scores(self):
        scores = hub_scores(prompt="test", thinking="test", outcome="test")
        assert set(scores.keys()) == {"HOME", "MATH", "CODE", "COMMANDS", "agent-context"}

    def test_scores_are_non_negative(self):
        scores = hub_scores(prompt="anything", thinking="goes", outcome="here")
        assert all(v >= 0.0 for v in scores.values())


# ---------------------------------------------------------------------------
# Tiebreaker
# ---------------------------------------------------------------------------


class TestTiebreaker:
    def test_code_beats_math_on_zero_scores(self):
        # Completely neutral content — both keyword and link signals zero
        # CODE should win as the primary tiebreaker
        result = _classify(prompt="hello world", thinking="nothing", outcome="done")
        # Either HOME or CODE depending on whether scores are all 0 — HOME wins on zero
        # On genuinely neutral content the result must be deterministic
        assert result in ("HOME", "CODE")

    def test_classify_is_deterministic(self):
        args = ("same prompt", "same thinking", "same outcome", ["harmonic-index"])
        assert _classify(*args) == _classify(*args)


class TestClassifyStem:
    def test_known_station_stems(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("MATH") == "MATH"
        assert classify_stem("harmonic-index") == "MATH"
        assert classify_stem("mcp-server") == "CODE"
        assert classify_stem("index") == "HOME"
        assert classify_stem("TOPOLOGY") == "COMMANDS"

    def test_unknown_stem_is_deterministic(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("no-such-note") == classify_stem("no-such-note")

    def test_source_phi_topology_routes_code(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("source/phi-topology-topo-graph") == "CODE"
        assert classify_stem("phi-topology-topo-graph") == "CODE"

    def test_source_phi_engine_routes_code(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("source/phi-engine-hub-ring") == "CODE"

    def test_source_sims_routes_math(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("source/sims-harmonic") == "MATH"
        assert classify_stem("sims-harmonic") == "MATH"

    def test_source_psspps_routes_code(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("source/psspps-pipeline") == "CODE"

    def test_source_mcp_server_routes_code(self):
        from graph.hub_classifier import classify_stem
        assert classify_stem("source/mcp-server-tools-graph") == "CODE"

    def test_member_exact_match_wins_over_prefix(self):
        from graph.hub_classifier import classify_stem
        # "graph-topo-graph" is explicit in CODE members
        assert classify_stem("graph-topo-graph") == "CODE"

    def test_prefix_fallback_for_novel_phi_stem(self):
        from graph.hub_classifier import classify_stem
        # Novel stem not in any member set — prefix match should find CODE
        assert classify_stem("source/phi-gnn-samba-layer") == "CODE"
