# phi / ui / hyphal_library.py

#source #python

> path: phi/ui/hyphal_library.py  
> ext: .py  

---

# phi / ui / hyphal_library.py

phi.ui.hyphal_library — tree-building constants and helpers for GenreGraphView.

Shared by phi.ui.genre_graph (Tk) and phi.ui.qt.genre_graph (PySide6).

Tree structure produced by build_tree():

    tree[genre][subgenre_or_None][mood][artist] = [(path, title, dur_s), ...]

All leaf nodes are (path, title, dur_s) tuples where dur_s is a "M:SS" string.


Defines: _leaf_count, build_tree

---

## Semantic links

→ [[graph-node]]
→ [[models-genre-predictor]]
→ [[graph-source-extractor]]
→ [[graph-linker]]
→ [[graph-ingestion]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-utils-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-renderer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
