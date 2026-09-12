"""MCP tools: skills_list, skills_pull, skills_push — skills/rules sync."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server._gate import _pre_call
from mcp_server._state import _dom_queue, mcp

_REPO_ROOT = Path(__file__).parent.parent.parent
_SKILLS_DIR = _REPO_ROOT / ".cursor" / "skills"
_RULES_DIR = _REPO_ROOT / ".cursor" / "rules"


def _read_skills() -> dict[str, str]:
    """Read every SKILL.md under .cursor/skills/*/SKILL.md."""
    result: dict[str, str] = {}
    if not _SKILLS_DIR.is_dir():
        return result
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.is_file():
            result[skill_dir.name] = skill_file.read_text(encoding="utf-8")
    return result


def _read_rules() -> dict[str, str]:
    """Read every .mdc file under .cursor/rules/."""
    result: dict[str, str] = {}
    if not _RULES_DIR.is_dir():
        return result
    for rule_file in sorted(_RULES_DIR.glob("*.mdc")):
        result[rule_file.stem] = rule_file.read_text(encoding="utf-8")
    return result


@mcp.tool()
def skills_list() -> dict[str, Any]:
    """
    List all available skills and rules from the canonical repo location.

    Returns a dict with:
    - skills: mapping of skill name → SKILL.md content
    - rules:  mapping of rule name (without .mdc) → rule content
    """
    with _dom_queue.gate("skills_list"):
        if err := _pre_call("skills_list"):
            return err
        skills = _read_skills()
        rules = _read_rules()
        return {
            "skills": skills,
            "rules": rules,
            "skill_count": len(skills),
            "rule_count": len(rules),
            "skill_names": sorted(skills.keys()),
            "rule_names": sorted(rules.keys()),
        }


@mcp.tool()
def skills_pull(target_dir: str = "~/.cursor") -> dict[str, Any]:
    """
    Write canonical skills and rules to a target machine's Cursor config dir.

    Parameters
    ----------
    target_dir : destination directory (default ~/.cursor). ~ is expanded.

    Writes:
    - {target_dir}/skills/{name}/SKILL.md  for each skill
    - {target_dir}/rules/{name}.mdc        for each rule

    Returns a summary of files written.
    """
    with _dom_queue.gate("skills_pull"):
        if err := _pre_call("skills_pull"):
            return err

        dest = Path(target_dir).expanduser().resolve()
        skills_dest = dest / "skills"
        rules_dest = dest / "rules"

        skills = _read_skills()
        rules = _read_rules()

        written: list[str] = []
        errors: list[str] = []

        for name, content in skills.items():
            out_path = skills_dest / name / "SKILL.md"
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
                written.append(str(out_path))
            except Exception as exc:
                errors.append(f"{out_path}: {exc}")

        for name, content in rules.items():
            out_path = rules_dest / f"{name}.mdc"
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
                written.append(str(out_path))
            except Exception as exc:
                errors.append(f"{out_path}: {exc}")

        return {
            "target_dir": str(dest),
            "files_written": len(written),
            "written": written,
            "errors": errors,
            "ok": len(errors) == 0,
        }


@mcp.tool()
def skills_push(source_dir: str) -> dict[str, Any]:
    """
    Push locally edited skills/rules back into the canonical repo location.

    Parameters
    ----------
    source_dir : directory containing skills/ and/or rules/ subdirectories.
                 ~ is expanded.

    Reads:
    - {source_dir}/skills/{name}/SKILL.md → .cursor/skills/{name}/SKILL.md
    - {source_dir}/rules/{name}.mdc       → .cursor/rules/{name}.mdc

    Returns a summary of files written.
    """
    with _dom_queue.gate("skills_push"):
        if err := _pre_call("skills_push"):
            return err

        src = Path(source_dir).expanduser().resolve()
        src_skills = src / "skills"
        src_rules = src / "rules"

        written: list[str] = []
        errors: list[str] = []

        if src_skills.is_dir():
            for skill_dir in sorted(src_skills.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.is_file():
                    continue
                dest_path = _SKILLS_DIR / skill_dir.name / "SKILL.md"
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_text(
                        skill_file.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                    written.append(str(dest_path))
                except Exception as exc:
                    errors.append(f"{dest_path}: {exc}")

        if src_rules.is_dir():
            for rule_file in sorted(src_rules.glob("*.mdc")):
                dest_path = _RULES_DIR / rule_file.name
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_text(
                        rule_file.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                    written.append(str(dest_path))
                except Exception as exc:
                    errors.append(f"{dest_path}: {exc}")

        return {
            "source_dir": str(src),
            "files_written": len(written),
            "written": written,
            "errors": errors,
            "ok": len(errors) == 0,
        }
