"""Unit tests for /10 (rate_ten) scoring."""
from __future__ import annotations

from pathlib import Path

from mcp_server.tools.rate import score_tree


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


_GOOD_FOO = '''\
"""Tiny public module."""
from __future__ import annotations

def add(x: int, y: int) -> int:
    """Return x + y."""
    return x + y
'''

_GOOD_INIT = '''\
"""pkg public API."""
from .foo import add

__all__ = ["add"]
'''

_GOOD_TEST = '''\
from pkg.foo import add

def test_add():
    assert add(1, 2) == 3
'''

_BAD_MOD = '''\
from os import *

def stuff(a, b, c):
    x = 1
''' + ("    x += 1\n" * 200)


def test_good_package_scores_high(tmp_path: Path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", _GOOD_INIT)
    _write(pkg / "foo.py", _GOOD_FOO)
    _write(tmp_path / "tests" / "test_foo.py", _GOOD_TEST)

    result = score_tree(pkg, project_root=tmp_path, tests_root=tmp_path / "tests")
    assert result["out_of"] == 10
    assert result["n_files"] == 2
    assert result["score"] >= 8.0
    assert result["grade"] in {"solid", "excellent"}
    assert "error" not in result


def test_messy_module_scores_low(tmp_path: Path):
    mod = tmp_path / "mess.py"
    _write(mod, _BAD_MOD)

    result = score_tree(mod, project_root=tmp_path, tests_root=tmp_path / "tests")
    assert result["score"] <= 5.5
    assert result["grade"] in {"rough", "weak"}
    assert result["axes"]["imports"]["pts"] < 1.0
    assert result["fixes"]


def test_empty_dir_is_zero(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = score_tree(empty, project_root=tmp_path)
    assert result["score"] == 0.0
    assert result["error"] == "no_python_files"


def test_score_clamped(tmp_path: Path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", _GOOD_INIT)
    _write(pkg / "foo.py", _GOOD_FOO)
    _write(tmp_path / "tests" / "test_foo.py", _GOOD_TEST)
    result = score_tree(pkg, project_root=tmp_path, tests_root=tmp_path / "tests")
    assert 0.0 <= result["score"] <= 10.0
