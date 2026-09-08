"""Unit tests for slash-command catalog, parser, and pre-hook handlers."""
from __future__ import annotations

import json

import pytest

from mcp_server.command_files import (
    EXTRA_CONTRACTS,
    PALETTE_SLASHES,
    check_command_files,
    render_files,
    sync_command_files,
)
from mcp_server.commands import (
    CATALOG,
    DO_SUBS,
    READ_SUBS,
    TOOL_TO_SLASH,
    CommandParseError,
    alias_map,
    handle_mcp_pre,
    handle_shell,
    handle_submit_prompt,
    list_catalog,
    parse_command,
    slash_for_tool,
)
from mcp_server.hooks import HookViolation, REGISTRY


class TestParse:
    def test_sim_positional(self):
        p = parse_command("/sim 1.5")
        assert p.tool == "double_well_sim"
        assert p.kwargs == {"x0": 1.5}

    def test_sim_embedded_in_prompt(self):
        p = parse_command("please run /sim -2.0 then report")
        assert p.kwargs["x0"] == -2.0

    def test_inject(self):
        p = parse_command("/inject 0 1.0")
        assert p.tool == "harmonic_inject"
        assert p.kwargs == {"shard_index": 0, "value": 1.0}

    def test_psspps_rest_query(self):
        p = parse_command("/psspps what is the Lambert W fixed point")
        assert p.tool == "psspps_query"
        assert p.kwargs["query"] == "what is the Lambert W fixed point"

    def test_psspps_requires_query(self):
        with pytest.raises(CommandParseError):
            parse_command("/psspps")

    def test_graph_commit_pipes(self):
        p = parse_command("/graph-commit did X | thought Y | built Z")
        assert p.tool == "graph_commit"
        assert p.kwargs["prompt"] == "did X"
        assert p.kwargs["thinking"] == "thought Y"
        assert p.kwargs["outcome"] == "built Z"

    def test_test_cov_flag(self):
        p = parse_command("/test --cov")
        assert p.tool == "run_tests"
        assert p.kwargs.get("coverage") is True

    def test_workflow_dev(self):
        p = parse_command("/dev")
        assert p.kind == "workflow"
        assert p.context_file == ".agent-context/dev.md"

    def test_cairrn_bare_is_hub_state(self):
        p = parse_command("/cairrn")
        assert p.tool == "hub_state"

    def test_cairrn_run(self):
        p = parse_command("/cairrn HOME 1.0")
        assert p.tool == "cairrn_hub_run"
        assert p.kwargs["hub_name"] == "HOME"
        assert p.kwargs["metric"] == 1.0

    def test_unknown(self):
        with pytest.raises(CommandParseError, match="unknown command"):
            parse_command("/not-a-real-command")

    def test_bare_name_without_slash(self):
        p = parse_command("index")
        assert p.tool == "harmonic_index_state"

    def test_rate_ten_bare(self):
        p = parse_command("/10")
        assert p.tool == "rate_ten"
        assert p.kwargs == {}
        assert p.module == "mcp_server.tools.rate"

    def test_rate_ten_target(self):
        p = parse_command("/10 phi/core")
        assert p.tool == "rate_ten"
        assert p.kwargs == {"target": "phi/core"}

    def test_rate_ten_embedded(self):
        p = parse_command("please run /10 mcp_server then report")
        assert p.tool == "rate_ten"
        assert p.kwargs["target"] == "mcp_server"


class TestCatalog:
    def test_unique_slashes(self):
        slashes = [s.slash for s in CATALOG.values()]
        assert len(slashes) == len(set(slashes))

    def test_list_catalog_primary(self):
        rows = list_catalog()
        cmds = {r["command"] for r in rows}
        assert cmds >= {"/read", "/do", "/dev", "/talk"}
        assert "/sim" not in cmds
        assert "/index" not in cmds
        read = next(r for r in rows if r["command"] == "/read")
        assert read["kind"] == "dispatcher"
        assert any(s["sub"] == "index" for s in read["subcommands"])
        do = next(r for r in rows if r["command"] == "/do")
        assert any(s["sub"] == "sim" for s in do["subcommands"])

    def test_list_catalog_aliases(self):
        rows = list_catalog(aliases=True)
        cmds = {r["command"] for r in rows}
        assert "/sim" in cmds
        assert "/dev" in cmds
        assert "/do" in cmds
        assert len(rows) == len(CATALOG)

    def test_umbrella_targets_exist(self):
        for slash in (*READ_SUBS.values(), *DO_SUBS.values()):
            assert slash in CATALOG, slash

    def test_alias_map_roundtrip(self):
        aliases = alias_map()
        assert aliases["/index"] == "/read index"
        assert aliases["/sim"] == "/do sim"
        assert aliases["/graph-commit"] == "/do commit"

    def test_tool_alias_roundtrip(self):
        assert slash_for_tool("double_well_sim") == "/sim"
        assert slash_for_tool("run_command") is None
        assert "graph_commit" in TOOL_TO_SLASH


class TestUmbrella:
    def test_read_index(self):
        p = parse_command("/read index")
        assert p.tool == "harmonic_index_state"
        assert p.kwargs == {}

    def test_read_legacy_slash_as_sub(self):
        p = parse_command("/read hub-state")
        assert p.tool == "hub_state"

    def test_read_psspps(self):
        p = parse_command("/read psspps Lambert W fixed point")
        assert p.tool == "psspps_query"
        assert p.kwargs["query"] == "Lambert W fixed point"

    def test_read_bare_is_workflow(self):
        p = parse_command("/read")
        assert p.kind == "workflow"
        assert p.context_file == ".agent-context/read.md"
        assert p.kwargs == {}

    def test_read_topic_is_workflow(self):
        p = parse_command("/read math")
        assert p.kind == "workflow"
        assert p.kwargs.get("topic") == "math"

    def test_read_help_lists(self):
        p = parse_command("/read help")
        assert p.kind == "dispatcher"
        assert any(s["sub"] == "status" for s in p.kwargs["subcommands"])

    def test_do_sim(self):
        p = parse_command("/do sim 1.5")
        assert p.tool == "double_well_sim"
        assert p.kwargs == {"x0": 1.5}

    def test_do_inject(self):
        p = parse_command("/do inject 0 1.0")
        assert p.tool == "harmonic_inject"
        assert p.kwargs == {"shard_index": 0, "value": 1.0}

    def test_do_commit_pipes(self):
        p = parse_command("/do commit did X | thought Y | built Z")
        assert p.tool == "graph_commit"
        assert p.kwargs["prompt"] == "did X"

    def test_do_10(self):
        p = parse_command("/do 10 phi/core")
        assert p.tool == "rate_ten"
        assert p.kwargs == {"target": "phi/core"}

    def test_do_bare_lists(self):
        p = parse_command("/do")
        assert p.kind == "dispatcher"
        assert any(s["sub"] == "sim" for s in p.kwargs["subcommands"])

    def test_do_unknown(self):
        with pytest.raises(CommandParseError, match="unknown /do subcommand"):
            parse_command("/do nope")

    def test_legacy_alias_still_parses(self):
        p = parse_command("/sim 1.5")
        assert p.tool == "double_well_sim"
        assert p.kwargs["x0"] == 1.5


class TestHookHandlers:
    def test_prompt_injects_dispatch(self):
        out = handle_submit_prompt({"prompt": "/sim 1.5"})
        assert out["continue"] is True
        ctx = out["additional_context"]
        assert "run_command" in ctx
        assert "double_well_sim" in ctx
        assert "x0=1.5" in ctx

    def test_prompt_read_index(self):
        out = handle_submit_prompt({"prompt": "/read index"})
        ctx = out["additional_context"]
        assert "run_command" in ctx
        assert "harmonic_index_state" in ctx

    def test_prompt_do_bare_is_dispatcher(self):
        out = handle_submit_prompt({"prompt": "/do"})
        ctx = out["additional_context"]
        assert "DISPATCHER /do" in ctx

    def test_prompt_without_command_is_silent(self):
        out = handle_submit_prompt({"prompt": "explain the harmonic index"})
        assert out == {"continue": True}

    def test_shell_denies_slash(self):
        out = handle_shell({"command": "/sim 1.5"})
        assert out["permission"] == "deny"
        assert "run_command" in out["agent_message"]

    def test_shell_denies_do(self):
        out = handle_shell({"command": "/do sim 1.5"})
        assert out["permission"] == "deny"

    def test_shell_allows_normal(self):
        out = handle_shell({"command": "ls Spotify-rip"})
        assert out["permission"] == "allow"

    def test_mcp_pre_annotates(self):
        out = handle_mcp_pre({"server": "spotify-rip", "tool": "double_well_sim"})
        assert out["permission"] == "allow"
        assert "/sim" in out["agent_message"]


class TestCommandDispatchHook:
    def test_empty_command_violates(self):
        from mcp_server._gate import _register_command_dispatch

        _register_command_dispatch()
        names = [h.name for h in REGISTRY._chain]
        assert "command_dispatch" in names
        with pytest.raises(HookViolation, match="non-empty"):
            REGISTRY.run("run_command", {"command": ""})

    def test_unknown_command_violates(self):
        from mcp_server._gate import _register_command_dispatch

        _register_command_dispatch()
        with pytest.raises(HookViolation, match="unknown command"):
            REGISTRY.run("run_command", {"command": "/nope"})

    def test_valid_command_passes(self):
        from mcp_server._gate import _register_command_dispatch

        _register_command_dispatch()
        results = REGISTRY.run("run_command", {"command": "/index"})
        assert any(r.name == "command_dispatch" and r.passed for r in results)


class TestCommandFiles:
    def test_render_covers_catalog_workflows_and_palette(self):
        files = render_files()
        for spec in CATALOG.values():
            if spec.kind == "workflow" and spec.context_file:
                assert spec.context_file in files
                assert files[spec.context_file].startswith("# /")
        for slash in PALETTE_SLASHES:
            rel = f".cursor/commands/{slash}.md"
            assert rel in files
            assert files[rel].startswith("---\n")
            assert "description:" in files[rel].split("---", 2)[1]
        read_palette = files[".cursor/commands/read.md"]
        assert "/read <sub>" in read_palette or "`index`" in read_palette
        assert "harmonic_index_state" in read_palette
        do_palette = files[".cursor/commands/do.md"]
        assert "double_well_sim" in do_palette
        for extra in EXTRA_CONTRACTS:
            assert f".agent-context/{extra}.md" in files
        assert ".cursor/rules/slash-commands.mdc" in files
        assert ".cursor/hooks/command-hook.sh" in files

    def test_sync_idempotent(self, tmp_path):
        first = sync_command_files(tmp_path)
        assert first["n_written"] == first["n_total"]
        second = sync_command_files(tmp_path)
        assert second["n_written"] == 0
        assert second["n_unchanged"] == first["n_total"]
        assert check_command_files(tmp_path) == []

    def test_repo_command_files_match_catalog(self):
        problems = check_command_files()
        assert problems == [], problems


def test_hook_json_roundtrip():
    """Cursor hooks must emit a single JSON object."""
    from mcp_server.commands import hook_main

    payload = json.dumps({"prompt": "/status"})
    # hook_main with explicit payload
    out = hook_main("prompt", json.loads(payload))
    json.dumps(out)
    assert out.get("continue") is True
    assert "run_command" in out.get("additional_context", "")
