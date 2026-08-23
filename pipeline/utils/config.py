"""
pipeline.utils.config — YAML + .env config loader.

Usage
-----
    from pipeline.utils.config import load_config
    cfg = load_config()                        # uses default config/config.yaml
    cfg = load_config(Path("my/config.yaml"))  # explicit path
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

_DEFAULT_CONFIG: Path = Path(__file__).parents[2] / "config" / "config.yaml"


def _deep_get(d: dict, *keys: str, default: Any = None) -> Any:
    """Nested dict access: _deep_get(cfg, 'vpn', 'timeout_s', default=30)."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


class Config:
    """
    Thin wrapper around the parsed YAML dict with attribute-style access.

    Sections are exposed as sub-Config objects:
        cfg.vpn.enabled
        cfg.download.output_dir
        cfg.workers.n_threads
    """

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, name: str) -> "Config | Any":
        if name.startswith("_"):
            raise AttributeError(name)
        val = self._data.get(name)
        if isinstance(val, dict):
            return Config(val)
        return val

    def get(self, *keys: str, default: Any = None) -> Any:
        return _deep_get(self._data, *keys, default=default)

    def as_dict(self) -> dict:
        return dict(self._data)

    def __repr__(self) -> str:
        keys = list(self._data.keys())
        return f"<Config sections={keys}>"


def load_config(path: Path = _DEFAULT_CONFIG) -> Config:
    """
    Load config.yaml and .env, return a Config object.

    .env is loaded first (if python-dotenv is available), so env vars set
    there are visible to os.environ before any code uses them.

    Parameters
    ----------
    path : Path to config.yaml (default: config/config.yaml relative to repo root)

    Returns
    -------
    Config — parsed YAML wrapped in attribute-access Config object

    Raises
    ------
    FileNotFoundError  if path doesn't exist
    RuntimeError       if pyyaml is not installed
    """
    if not _YAML_AVAILABLE:
        raise RuntimeError("pyyaml is not installed — run: pip install pyyaml")

    # Load .env from repo root (sibling of config/)
    env_path = path.parent.parent / ".env"
    if _DOTENV_AVAILABLE and env_path.exists():
        load_dotenv(env_path, override=False)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return Config(data)
