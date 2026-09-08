# /modular — Package cleanly

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Turn raw `/dev` output into a small, importable Python surface.

- One idea per module. Public names in `__init__.py`.
- No circular imports. No unused helpers left behind.
- Keep stdlib-only modules free of numpy / FastMCP unless they already depend on them.

## Done when

`python -c "from package import name"` works from the repo root, and tests import the same path.
