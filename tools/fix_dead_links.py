"""
fix_dead_links.py — prune every dead wikilink from the vault.

Strategy
--------
1. Load all .md files and build the set of valid stems (filename without .md).
2. For each file:
   a. Find every [[wikilink]] using the same regex as graph/node.py.
   b. A link is dead if its last path component (bare stem) is not in the stems set.
   c. Remove lines whose only content is `→ [[dead-link]]` or `→ [[dead-link]]`
      variants (the auto-linker format).
   d. For inline dead links that are mixed with real content, strip just the
      [[dead-link]] token.
3. Write the cleaned file back only if changed.
4. Print a summary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ── vault root (this script lives in tools/) ──────────────────────────────────
VAULT_ROOT = Path(__file__).parent.parent
_SKIP_DIRS = {".obsidian", "__pycache__", ".git", ".hub.git", ".pytest_cache"}

WIKILINK_RE = re.compile(r"\[\[([^\]|#\n]+?)(?:\|[^\]]+)?\]\]")


def load_stems() -> set[str]:
    stems: set[str] = set()
    for p in VAULT_ROOT.rglob("*.md"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        stems.add(p.stem)
    return stems


def is_dead(link: str, stems: set[str]) -> bool:
    bare = link.rsplit("/", 1)[-1]
    return bare not in stems


def clean_file(path: Path, stems: set[str]) -> tuple[int, list[str]]:
    """
    Returns (n_removed, dead_links_found) and writes cleaned content if changed.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    cleaned: list[str] = []
    removed = 0
    dead_found: list[str] = []

    for line in lines:
        links_in_line = WIKILINK_RE.findall(line)
        dead_in_line = [lnk for lnk in links_in_line if is_dead(lnk, stems)]

        if not dead_in_line:
            cleaned.append(line)
            continue

        # Check if the line is *only* a dead wikilink arrow line:
        # e.g.  "→ [[linker]]\n"  or  "→ [[linker]]  \n"
        stripped = line.strip()
        if re.fullmatch(r"→\s*\[\[[^\]]+\]\]\s*", stripped):
            # Whole line is the dead link — drop it entirely
            removed += 1
            dead_found.extend(dead_in_line)
            continue

        # Mixed line — strip only the dead [[link]] tokens, keep the rest
        new_line = line
        for d in dead_in_line:
            # Remove  [[dead-link]]  and the optional leading →  /space
            new_line = re.sub(
                r"→\s*\[\[" + re.escape(d) + r"\]\]\s*",
                "",
                new_line,
            )
            new_line = re.sub(r"\[\[" + re.escape(d) + r"\]\]", "", new_line)
        removed += len(dead_in_line)
        dead_found.extend(dead_in_line)
        # Only keep the line if there's something left (not just whitespace/arrows)
        if new_line.strip():
            cleaned.append(new_line)

    new_text = "".join(cleaned)
    # Collapse runs of 3+ blank lines down to 2
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")

    return removed, dead_found


def main() -> None:
    stems = load_stems()
    print(f"Vault stems loaded: {len(stems)}")

    total_removed = 0
    total_files = 0
    all_dead: list[str] = []

    for p in sorted(VAULT_ROOT.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        n, dead = clean_file(p, stems)
        if n:
            rel = p.relative_to(VAULT_ROOT)
            print(f"  {rel}: removed {n} dead link(s): {dead[:4]}{'…' if len(dead)>4 else ''}")
            total_removed += n
            total_files += 1
            all_dead.extend(dead)

    print(f"\nDone. Removed {total_removed} dead links across {total_files} files.")
    if total_removed == 0:
        print("Vault is already clean.")


if __name__ == "__main__":
    main()
