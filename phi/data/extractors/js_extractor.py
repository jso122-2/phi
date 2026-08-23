"""
JavaScript / TypeScript symbol extractor — regex-based (no tree-sitter dep).

Extracts:
  - Named functions:       function foo(
  - Arrow const:           const foo = (  /  const foo = async (
  - Class declarations:    class Foo  /  export class Foo
  - Export functions:      export function foo  /  export default function

JSDoc comment immediately above each match is captured as docstring.
Import statements are collected for connectivity edge detection.
"""
import os
import re
import logging
from typing import List, Optional, Tuple

from phi.data.symbol_node import SymbolNode

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────
_FUNC_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(",
    re.MULTILINE,
)
_ARROW_RE = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
    re.MULTILINE,
)
_CLASS_RE = re.compile(
    r"^(?:export\s+)?(?:default\s+)?class\s+(\w+)",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"""(?:import\s+.+?\s+from\s+['"](.+?)['"]|require\(['"](.+?)['"]\))""",
    re.MULTILINE,
)
_JSDOC_RE = re.compile(r"/\*\*(.*?)\*/\s*$", re.DOTALL)


class JSExtractor:
    """Extract SymbolNodes from .js / .ts / .jsx / .tsx files."""

    def extract(self, path: str, repo: Optional[str] = None) -> List[SymbolNode]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError:
            return []

        lang = "typescript" if path.endswith((".ts", ".tsx")) else "javascript"
        mtime = os.path.getmtime(path)
        imports = self._collect_imports(source)
        lines = source.splitlines()

        symbols: List[SymbolNode] = []
        seen: set = set()

        for pattern, kind in [
            (_FUNC_RE, "function"),
            (_ARROW_RE, "function"),
            (_CLASS_RE, "class"),
        ]:
            for m in pattern.finditer(source):
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)

                lineno = source[: m.start()].count("\n")
                sig = lines[lineno].strip() if lineno < len(lines) else ""
                doc = self._extract_jsdoc(source, m.start())
                snippet = "\n".join(lines[lineno: lineno + 25])

                symbols.append(SymbolNode(
                    path=path,
                    name=name,
                    kind=kind,
                    language=lang,
                    repo=repo,
                    signature=sig,
                    docstring=doc[:300],
                    body_snippet=snippet[:400],
                    imports=imports,
                    modified_ts=mtime,
                    created_ts=mtime,
                ))

        # Fallback: module-level node if nothing matched
        if not symbols:
            symbols.append(SymbolNode(
                path=path,
                name=os.path.basename(path),
                kind="module",
                language=lang,
                repo=repo,
                body_snippet=source[:400],
                imports=imports,
                modified_ts=mtime,
                created_ts=mtime,
            ))

        return symbols

    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _collect_imports(source: str) -> List[str]:
        names: List[str] = []
        for m in _IMPORT_RE.finditer(source):
            mod = m.group(1) or m.group(2)
            if mod and not mod.startswith("."):
                names.append(mod.split("/")[0])  # package root only
        return list(dict.fromkeys(names))

    @staticmethod
    def _extract_jsdoc(source: str, pos: int) -> str:
        """Find the JSDoc comment immediately before pos."""
        prefix = source[:pos].rstrip()
        m = _JSDOC_RE.search(prefix)
        if m:
            return re.sub(r"\s*\*\s*", " ", m.group(1)).strip()
        # Single-line // comment
        lines_before = prefix.splitlines()
        comment_lines = []
        for line in reversed(lines_before):
            stripped = line.strip()
            if stripped.startswith("//"):
                comment_lines.insert(0, stripped[2:].strip())
            else:
                break
        return " ".join(comment_lines)
