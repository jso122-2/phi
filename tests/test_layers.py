"""Corpus layers: stations / sessions / ingest."""
from __future__ import annotations

from graph.layers import (
    QUERY_LAYERS,
    layer_of,
    in_layers,
    phi_visible,
    STATION_HUB_STEMS,
)
from graph.linker import SIMILARITY_THRESHOLD
from graph.node import load_vault
from psspps.retriever import load_vault_docs


class TestLayerOf:
    def test_root_station(self):
        assert layer_of("HOME.md") == "stations"

    def test_music_is_stations(self):
        assert layer_of("music/VAULT.md") == "stations"

    def test_sessions_dir(self):
        assert layer_of("sessions/2026-07-13-foo.md") == "sessions"

    def test_keep_dir_is_ingest(self):
        assert layer_of("keep/some-note.md") == "ingest"

    def test_source_dir_is_ingest(self):
        assert layer_of("source/graph-worker.md") == "ingest"

    def test_root_keep_catalog_is_ingest(self):
        assert layer_of("keep.md") == "ingest"

    def test_query_layers_exclude_ingest(self):
        assert not in_layers("keep/foo.md", QUERY_LAYERS)
        assert in_layers("HOME.md", QUERY_LAYERS)
        assert in_layers("sessions/x.md", QUERY_LAYERS)


class TestLoadFilters:
    def test_query_load_skips_keep_source(self):
        nodes = load_vault(layers=QUERY_LAYERS)
        assert nodes
        assert all(layer_of(n.rel_path) != "ingest" for n in nodes)

    def test_psspps_default_skips_ingest(self):
        docs = load_vault_docs()
        assert docs
        assert all(not d["path"].startswith(("keep/", "source/")) for d in docs)
        assert all(d["path"] not in {"keep.md", "source.md"} for d in docs)

    def test_full_vault_still_loads_ingest(self):
        all_nodes = load_vault()
        query_nodes = load_vault(layers=QUERY_LAYERS)
        assert len(all_nodes) > len(query_nodes)


class TestStationHubs:
    def test_five_harmonic_stations_included(self):
        for stem in ("HOME", "MATH", "CODE", "COMMANDS", "agent-context"):
            assert stem in STATION_HUB_STEMS

    def test_music_ontology_included(self):
        assert "VAULT" in STATION_HUB_STEMS
        assert "ARTIST" in STATION_HUB_STEMS

    def test_keep_not_a_station_hub(self):
        assert "keep" not in STATION_HUB_STEMS

    def test_phi_is_a_station_hub(self):
        assert "phi" in STATION_HUB_STEMS

    def test_hub_math_qualifier_stripped_from_non_station(self):
        from graph.layers import _HUB_TOKEN
        text = "#session #prompt #hub-MATH\n"
        assert _HUB_TOKEN.search(text)
        assert _HUB_TOKEN.sub(lambda m: m.group(1), text).strip() == "#session #prompt"


class TestPhiVisible:
    def test_stations_are_visible(self):
        assert phi_visible("HOME.md")
        assert phi_visible("music/VAULT.md")

    def test_source_ingest_is_visible(self):
        assert phi_visible("source/phi-core-player.md")
        assert phi_visible("source/graph-worker.md")

    def test_keep_and_sessions_are_hidden(self):
        assert not phi_visible("keep/some-note.md")
        assert not phi_visible("sessions/x.md")
        assert not phi_visible("spotify-pipeline/fetcher.md")
        assert not phi_visible("agent-log/foo.md")


class TestThreshold:
    def test_auto_link_threshold_raised(self):
        assert SIMILARITY_THRESHOLD == 0.25
