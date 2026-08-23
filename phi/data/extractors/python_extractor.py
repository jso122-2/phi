"""
Python symbol extractor — uses stdlib ast.

One SymbolNode per top-level function, async function, class, and per-method
inside classes. Module-level imports are attached to every symbol in the file
(so the gate can check connectivity via import names).
"""
import ast
import os
import textwrap
import time
import logging
from typing import List, Optional

from phi.data.symbol_node import SymbolNode

logger = logging.getLogger(__name__)


class PythonExtractor:
    """Extract SymbolNodes from a single .py file via AST parsing."""

    def extract(self, path: str, repo: Optional[str] = None) -> List[SymbolNode]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError:
            return []

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            return []

        mtime = os.path.getmtime(path)
        file_imports = self._collect_imports(tree)
        lines = source.splitlines()

        symbols: List[SymbolNode] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip methods at this pass — collected via class traversal
                if self._is_method(node, tree):
                    continue
                sym = self._from_function(node, path, lines, file_imports, mtime, repo)
                if sym:
                    symbols.append(sym)

            elif isinstance(node, ast.ClassDef):
                # Class-level node
                sym = self._from_class(node, path, lines, file_imports, mtime, repo)
                if sym:
                    symbols.append(sym)
                # Methods inside the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        sym = self._from_function(
                            item, path, lines, file_imports, mtime, repo,
                            class_name=node.name,
                        )
                        if sym:
                            symbols.append(sym)

        # Fallback: if no symbols extracted, emit a module-level node
        if not symbols:
            snippet = "\n".join(lines[:30])
            symbols.append(SymbolNode(
                path=path,
                name=os.path.basename(path).replace(".py", ""),
                kind="module",
                language="python",
                repo=repo,
                signature=lines[0] if lines else "",
                docstring=ast.get_docstring(tree) or "",
                body_snippet=snippet[:400],
                imports=file_imports,
                modified_ts=mtime,
                created_ts=mtime,
            ))

        return symbols

    # ──────────────────────────────────────────────────────────────────────────

    def _from_function(
        self,
        node: ast.FunctionDef,
        path: str,
        lines: List[str],
        imports: List[str],
        mtime: float,
        repo: Optional[str],
        class_name: Optional[str] = None,
    ) -> Optional[SymbolNode]:
        qual_name = f"{class_name}.{node.name}" if class_name else node.name
        kind = "method" if class_name else "function"
        sig = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        doc = ast.get_docstring(node) or ""
        body = self._body_snippet(node, lines)

        # Decorator tags (e.g. @property, @staticmethod, @torch.no_grad)
        decorator_tags = self._collect_decorators(node)

        # Call graph: functions/methods called within this body
        calls = self._collect_calls(node)

        return SymbolNode(
            path=path,
            name=qual_name,
            kind=kind,
            language="python",
            repo=repo,
            signature=sig,
            docstring=doc[:300],
            body_snippet=body[:1200],
            imports=imports,
            tags=decorator_tags,
            calls=calls,
            modified_ts=mtime,
            created_ts=mtime,
        )

    def _from_class(
        self,
        node: ast.ClassDef,
        path: str,
        lines: List[str],
        imports: List[str],
        mtime: float,
        repo: Optional[str],
    ) -> Optional[SymbolNode]:
        sig = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        doc = ast.get_docstring(node) or ""
        body = self._body_snippet(node, lines, max_lines=40)

        # Decorator tags
        decorator_tags = self._collect_decorators(node)

        # Inheritance — base class names for inheritance edge building
        bases = self._collect_bases(node)

        return SymbolNode(
            path=path,
            name=node.name,
            kind="class",
            language="python",
            repo=repo,
            signature=sig,
            docstring=doc[:300],
            body_snippet=body[:1200],
            imports=imports,
            tags=decorator_tags,
            bases=bases,
            modified_ts=mtime,
            created_ts=mtime,
        )

    @staticmethod
    def _body_snippet(node: ast.AST, lines: List[str], max_lines: int = 60) -> str:
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", start + max_lines)
        snippet = "\n".join(lines[start:min(end, start + max_lines)])
        return textwrap.dedent(snippet)

    @staticmethod
    def _collect_imports(tree: ast.Module) -> List[str]:
        """Return all imported names/modules referenced at module scope."""
        names: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.append(node.module)
                for alias in node.names:
                    names.append(alias.asname or alias.name)
        return list(dict.fromkeys(names))  # dedupe, preserve order

    @staticmethod
    def _collect_calls(node: ast.AST) -> List[str]:
        """
        Collect names of all functions/methods directly called within this node.
        Skips builtins and dunder methods to reduce noise.
        """
        _NOISE = frozenset({
            "print", "len", "range", "enumerate", "zip", "map", "filter",
            "list", "dict", "set", "tuple", "str", "int", "float", "bool",
            "isinstance", "hasattr", "getattr", "setattr", "super",
            "append", "extend", "update", "get", "items", "keys", "values",
        })
        names: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id not in _NOISE:
                    names.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    attr = child.func.attr
                    if not (attr.startswith("__") and attr.endswith("__")) and attr not in _NOISE:
                        names.append(attr)
        return list(dict.fromkeys(names))[:20]  # dedupe, cap at 20

    @staticmethod
    def _collect_bases(node: ast.ClassDef) -> List[str]:
        """Return base class names for inheritance edge building."""
        bases: List[str] = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        return bases

    @staticmethod
    def _collect_decorators(node: ast.AST) -> List[str]:
        """Return decorator names as tags."""
        tags: List[str] = []
        decorator_list = getattr(node, "decorator_list", [])
        for dec in decorator_list:
            if isinstance(dec, ast.Name):
                tags.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                tags.append(dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    tags.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    tags.append(dec.func.attr)
        return tags

    @staticmethod
    def _is_method(node: ast.FunctionDef, tree: ast.Module) -> bool:
        """True if node appears inside a ClassDef in the module."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in ast.walk(parent):
                    if child is node:
                        return True
        return False
