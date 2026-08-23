"""
SymbolNode — the universal graph node for the Samba unified graph.

Generalises NoteNode (Obsidian-specific) to cover code symbols (functions,
classes, methods), markdown notes, and config files. Every node in the
UnifiedGraph is a SymbolNode.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SymbolNode:
    """
    A single node in the unified knowledge graph.

    Fields common with NoteNode (backwards-compatible):
        path            Absolute path to the source file
        node_id         Integer index in the graph (assigned by UnifiedGraph)
        modified_ts     File mtime in epoch seconds
        created_ts      Best-effort creation timestamp
        tags            Language tags, decorators, or Obsidian #tags

    New fields:
        name            Qualified symbol name (e.g. "MyClass.my_method" or note title)
        kind            "function" | "class" | "method" | "note" | "config" | "module"
        language        "python" | "javascript" | "typescript" | "markdown" | "yaml" |
                        "json" | "toml" | "unknown"
        repo            Absolute path to the nearest git repo root, or None
        signature       First line of the symbol definition (or note heading)
        docstring       Extracted docstring / JSDoc / YAML comment (first 300 chars)
        body_snippet    First 400 chars of the symbol body (for encoder input)
        imports         Names imported within this file's scope (for import edge detection)
        outlinks        Wikilinks for markdown notes (empty for code symbols)
        admitted        Set by AutonomousGate: True = in graph, False = gate-rejected
        gate_score      Confidence score from AutonomousGate (0–1)
    """

    path: str
    name: str
    kind: str
    language: str

    node_id: int = -1
    repo: Optional[str] = None
    signature: str = ""
    docstring: str = ""
    body_snippet: str = ""
    imports: List[str] = field(default_factory=list)
    outlinks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_ts: float = 0.0
    modified_ts: float = 0.0
    # ── Structural depth fields ───────────────────────────────────────────────
    # Populated by extractors; used by UnifiedGraph for call/inheritance edges.
    calls: List[str] = field(default_factory=list)   # function/method names called within this symbol
    bases: List[str] = field(default_factory=list)   # base class names (inheritance)
    subheadings: List[str] = field(default_factory=list)  # H2/H3 headings inside a note/doc

    admitted: bool = True
    gate_score: float = 1.0

    @property
    def title(self) -> str:
        """Alias for NoteNode compatibility — used by MCP coherence tools."""
        return self.name

    @property
    def encoding_text(self) -> str:
        """
        Structured text fed to the encoder.

        Format:
            '<language> <kind>: <name>
             [bases: ...]           (classes only)
             [calls: ...]           (functions/methods only)
             <docstring>
             [subheadings: ...]     (notes/docs only)
             <body_snippet>'
        """
        prefix = f"{self.language} {self.kind}: {self.name}"
        parts = [prefix]
        if self.bases:
            parts.append(f"inherits: {', '.join(self.bases[:4])}")
        if self.calls:
            parts.append(f"calls: {', '.join(self.calls[:8])}")
        if self.docstring:
            parts.append(self.docstring[:300])
        if self.subheadings:
            parts.append("sections: " + " | ".join(self.subheadings[:6]))
        if self.body_snippet:
            parts.append(self.body_snippet[:500])
        return "\n".join(parts)

    @property
    def content_snippet(self) -> str:
        """NoteNode compatibility — encoding_text alias."""
        return self.encoding_text

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.body_snippet.encode()).hexdigest()
