"""
Ingestion pipeline — embed, link, classify, write, manifest.

The single reusable core for pushing any document collection into the
Obsidian vault graph.  Works as a library (imported by keep_ingest.py,
ingest.py, or future importers) or stand-alone.

Architecture
------------
  IngestedDoc      — input: one document to ingest (title, text, tags, meta)
  IngestionManifest — output: written nodes, hub counts, semantic stats
  IngestionPipeline — orchestrator

Pipeline stages per document
-----------------------------
  1. Embed       — MiniLM all-MiniLM-L6-v2 vector (sentence-transformers or
                   fastembed, same model)
  2. Link        — cosine similarity → top-K existing vault nodes above threshold
  3. Classify    — hub_classifier() → HOME | MATH | CODE | COMMANDS | agent-context
  4. Write       — write <output_dir>/<timestamp>-<slug>.md to disk

Pipeline stages for the batch
------------------------------
  5. Cross-link  — within-batch cosine similarity → related-doc wikilinks
  6. Manifest    — write <output_dir>/ingest-manifest.json with hub counts and
                   node list; the MCP tool graph_sync_manifest reads this to
                   pulse the harmonic index

The manifest is the bridge between file I/O (this module, any Python env)
and index injection (MCP server, spotify-rip env).  The two sides are
deliberately decoupled so ingestion never requires a live MCP session.

Embedding backend priority
--------------------------
  1. sentence-transformers (full PyTorch; installed in mamba base env)
  2. fastembed (ONNX; installed in spotify-rip env)
  Both produce identical all-MiniLM-L6-v2 384-dim normalised vectors.

Usage
-----
    from graph.ingestion import IngestedDoc, IngestionPipeline

    docs = [IngestedDoc(title="Note A", text="..."), ...]
    pipeline = IngestionPipeline(output_dir=VAULT_ROOT / "keep")
    manifest = pipeline.run(docs)
    print(manifest.summary())
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Package root resolution — works whether imported or run directly
# ---------------------------------------------------------------------------

_PACKAGE_ROOT = Path(__file__).parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from graph.hub_classifier import classify_hub
from graph.layers import LAYERS
from graph.node import VAULT_ROOT
from psspps.retriever import _clean as _vault_clean, load_vault_docs

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MANIFEST_FILENAME = "ingest-manifest.json"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class IngestedDoc:
    """One document to be ingested into the vault."""
    title: str
    text: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional: pre-assign filename stem (auto-generated if empty)
    stem_override: str = ""


@dataclass
class WrittenNode:
    """Result record for one written vault node."""
    stem: str
    path: str                   # relative to VAULT_ROOT
    hub: str
    semantic_links: list[str]   # links to existing vault nodes
    cross_links: list[str]      # links to other docs in this batch


@dataclass
class IngestionManifest:
    """Full result of an ingestion run — written to disk as JSON."""
    output_dir: str
    n_written: int
    n_skipped: int
    backend: str
    threshold: float
    top_k: int
    hub_counts: dict[str, int]  # hub_name → number of docs classified there
    nodes: list[WrittenNode]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def summary(self) -> str:
        lines = [
            f"Ingestion complete — {self.n_written} written, {self.n_skipped} skipped",
            f"  backend: {self.backend}   threshold: {self.threshold}   top_k: {self.top_k}",
            f"  hub distribution: { {k: v for k, v in sorted(self.hub_counts.items())} }",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["nodes"] = [asdict(n) for n in self.nodes]
        return d


# ---------------------------------------------------------------------------
# Embedding backend
# ---------------------------------------------------------------------------


def _build_encoder() -> tuple:
    """Return (encode_fn, backend_name).  encode_fn(texts) -> np.ndarray (N, 384)."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
        model = SentenceTransformer("all-MiniLM-L6-v2")

        def _st_encode(texts: list[str]) -> np.ndarray:
            return np.array(
                model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=64),
                dtype=np.float32,
            )

        return _st_encode, "sentence-transformers"
    except ImportError:
        pass

    try:
        from psspps.embedder import embed as _fe_embed
        return _fe_embed, "fastembed"
    except ImportError:
        pass

    raise RuntimeError(
        "No embedding backend found.\n"
        "  mamba install -n base -c conda-forge sentence-transformers  (PyTorch)\n"
        "  pip install fastembed                                        (ONNX)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(text: str, max_len: int = 48) -> str:
    return _SLUG_RE.sub("-", text.lower()[:max_len]).strip("-") or "untitled"


def _cosine_top_k(
    query_vec: np.ndarray,
    corpus_vecs: np.ndarray,
    corpus_ids: list[str],
    threshold: float,
    top_k: int,
    exclude: set[str],
) -> list[str]:
    """Return top-K corpus_ids by cosine similarity, above threshold, not in exclude."""
    sims = corpus_vecs.astype(np.float64) @ query_vec.astype(np.float64)
    order = np.argsort(sims)[::-1]
    results: list[str] = []
    for idx in order:
        if len(results) >= top_k:
            break
        if float(sims[idx]) < threshold:
            break
        cid = corpus_ids[idx]
        if cid not in exclude:
            results.append(cid)
    return results


def _render_node(
    doc: IngestedDoc,
    stem: str,
    semantic_links: list[str],
    cross_links: list[str],
    output_dir_name: str,
) -> str:
    tag_line = " ".join(f"#{t}" for t in (doc.tags or ["imported"]))

    meta_lines: list[str] = []
    for k, v in doc.metadata.items():
        meta_lines.append(f"> {k}: {v}  ")

    lines: list[str] = [
        f"# {doc.title or stem.replace('-', ' ').title()}",
        "",
        tag_line,
        "",
    ]

    if meta_lines:
        lines += meta_lines + [""]

    lines += ["---", ""]

    if doc.text:
        lines += [doc.text.strip(), ""]

    lines += ["---", ""]

    if semantic_links:
        lines += ["## Semantic links", ""]
        for lnk in semantic_links:
            lines.append(f"→ [[{lnk}]]")
        lines.append("")

    if cross_links:
        lines += ["## Related notes", ""]
        for lnk in cross_links:
            lines.append(f"→ [[{lnk}]]")
        lines.append("")

    lines += [
        f"→ [[{output_dir_name}]] — import index  ",
        "",
        "*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# IngestionPipeline
# ---------------------------------------------------------------------------


class IngestionPipeline:
    """
    Embed, link, classify, and write a batch of documents into the vault graph.

    Parameters
    ----------
    output_dir   : vault subdirectory to write nodes into (e.g. VAULT_ROOT/"keep")
    threshold    : minimum cosine similarity for a link to be injected (default 0.30)
    top_k        : max links per document (default 5)
    cross_link   : if True, cross-link docs within the batch to each other
    encoder      : optional pre-built encode_fn; built automatically if None
    """

    def __init__(
        self,
        output_dir: Path,
        threshold: float = 0.30,
        top_k: int = 5,
        cross_link: bool = True,
        encoder=None,
    ) -> None:
        self.output_dir = output_dir
        self.threshold = threshold
        self.top_k = top_k
        self.cross_link = cross_link

        if encoder is not None:
            self._encode, self._backend = encoder, "external"
        else:
            self._encode, self._backend = _build_encoder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        docs: list[IngestedDoc],
        *,
        wipe_output_dir: bool = False,
        exclude_dirs: set[str] | None = None,
    ) -> IngestionManifest:
        """
        Run the full ingestion pipeline.

        Parameters
        ----------
        docs             : documents to ingest
        wipe_output_dir  : if True, delete and recreate output_dir before writing
        exclude_dirs     : vault subdirectory names to exclude from corpus
                           (default: {output_dir.name} to avoid self-linking)
        """
        if not docs:
            return IngestionManifest(
                output_dir=str(self.output_dir.relative_to(VAULT_ROOT)),
                n_written=0, n_skipped=0, backend=self._backend,
                threshold=self.threshold, top_k=self.top_k,
                hub_counts={}, nodes=[],
            )

        _excl = exclude_dirs if exclude_dirs is not None else {self.output_dir.name}

        # ── Prepare output dir ────────────────────────────────────────────
        if wipe_output_dir and self.output_dir.exists():
            import shutil
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # ── Load + embed existing vault corpus ────────────────────────────
        print("Loading vault corpus...", file=sys.stderr)
        vault_docs = load_vault_docs(layers=LAYERS)
        corpus_docs = [d for d in vault_docs if not any(
            d["path"].startswith(ex + "/") or d["path"].startswith(ex + "\\")
            for ex in _excl
        )]
        corpus_texts = [_vault_clean(d["clean_text"]) for d in corpus_docs]
        corpus_ids = [d["title"] for d in corpus_docs]
        print(f"  {len(corpus_docs)} existing vault nodes", file=sys.stderr)

        print("Embedding corpus...", file=sys.stderr)
        corpus_vecs = self._encode(corpus_texts) if corpus_texts else np.zeros((0, 384), dtype=np.float32)

        # ── Embed all input docs in one batch ─────────────────────────────
        print(f"Embedding {len(docs)} input documents...", file=sys.stderr)
        doc_texts_raw = [f"{d.title} {d.text}" for d in docs]
        # Strip non-ASCII so embedding doesn't choke on emoji-heavy notes
        doc_texts = [re.sub(r"[^\x00-\x7F]+", " ", t) for t in doc_texts_raw]
        doc_vecs = self._encode(doc_texts)
        print(f"  done — shape {doc_vecs.shape}", file=sys.stderr)

        # ── Per-doc: link + classify + write ──────────────────────────────
        stems: list[str] = []
        written: list[WrittenNode] = []
        hub_counts: dict[str, int] = {}

        for i, doc in enumerate(docs):
            vec = doc_vecs[i]
            stem = self._make_stem(doc, i)
            exclude_set = {stem}

            sem_links = _cosine_top_k(
                vec, corpus_vecs, corpus_ids,
                threshold=self.threshold, top_k=self.top_k,
                exclude=exclude_set,
            ) if len(corpus_vecs) > 0 else []

            hub = classify_hub(doc.title, doc.text, "", discovered_links=sem_links)
            hub_counts[hub] = hub_counts.get(hub, 0) + 1

            stems.append(stem)
            written.append(WrittenNode(
                stem=stem,
                path=str((self.output_dir / f"{stem}.md").relative_to(VAULT_ROOT)),
                hub=hub,
                semantic_links=sem_links,
                cross_links=[],   # filled in cross-link pass
            ))

        # ── Cross-link pass ───────────────────────────────────────────────
        if self.cross_link and len(doc_vecs) > 1:
            print("Cross-linking batch...", file=sys.stderr)
            cross_total = 0
            for i, node in enumerate(written):
                q = doc_vecs[i]
                exclude_set = {node.stem}
                cross = _cosine_top_k(
                    q, doc_vecs, stems,
                    threshold=self.threshold, top_k=self.top_k,
                    exclude=exclude_set,
                )
                node.cross_links = [f"{self.output_dir.name}/{s}" for s in cross]
                cross_total += len(cross)
            print(f"  {cross_total} cross-links", file=sys.stderr)

        # ── Write files ───────────────────────────────────────────────────
        print("Writing vault nodes...", file=sys.stderr)
        out_dir_name = self.output_dir.name
        for doc, node in zip(docs, written):
            content = _render_node(doc, node.stem, node.semantic_links, node.cross_links, out_dir_name)
            (self.output_dir / f"{node.stem}.md").write_text(content, encoding="utf-8")

        # ── Build and save manifest ───────────────────────────────────────
        manifest = IngestionManifest(
            output_dir=str(self.output_dir.relative_to(VAULT_ROOT)),
            n_written=len(written),
            n_skipped=0,
            backend=self._backend,
            threshold=self.threshold,
            top_k=self.top_k,
            hub_counts=hub_counts,
            nodes=written,
        )
        self._write_manifest(manifest)
        print(f"Manifest → {self.output_dir / _MANIFEST_FILENAME}", file=sys.stderr)

        return manifest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_stem(self, doc: IngestedDoc, idx: int) -> str:
        if doc.stem_override:
            return doc.stem_override
        ts = doc.metadata.get("created_ts", "")
        if not ts:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        slug = _slug(doc.title) if doc.title else f"doc-{idx:04d}"
        return f"{ts}-{slug}"

    def _write_manifest(self, manifest: IngestionManifest) -> None:
        path = self.output_dir / _MANIFEST_FILENAME
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Index node writer (separate from pipeline — called by importers)
# ---------------------------------------------------------------------------


def write_import_index(
    output_dir: Path,
    stems: list[str],
    source_label: str = "import",
) -> Path:
    """Write/overwrite <output_dir>/index.md listing all imported nodes."""
    link_lines = "\n".join(f"→ [[{output_dir.name}/{s}]]" for s in sorted(stems))
    content = f"""# {output_dir.name} — {source_label}

#hub #{output_dir.name.replace("-", "")} #imported

> {len(stems)} notes imported.  
> Links discovered via MiniLM all-MiniLM-L6-v2 semantic similarity.

---

## Notes

{link_lines}

---

→ [[HOME]] ← grand central  
→ [[graph]] — graph worker hub

*Generated by `graph/ingestion.py`*
"""
    out = output_dir / "index.md"
    out.write_text(content, encoding="utf-8")
    return out
