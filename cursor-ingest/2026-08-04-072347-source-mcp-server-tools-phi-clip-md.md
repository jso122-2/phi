# source / mcp-server-tools-phi-clip.md

#doc #md

> path: source/mcp-server-tools-phi-clip.md  
> ext: .md  

---

# mcp_server/tools/phi_clip

#code #module #mcp-server #code

> source_path: mcp_server/tools/phi_clip.py  
> package: mcp_server  
> module: mcp_server/tools/phi_clip  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/phi_clip`  
**Source:** `mcp_server/tools/phi_clip.py`

phi_clip — MCP tool: gemini_clip (Stage III track clipper via P_sps).

## API

- `def _get_session` — Build and cache the PhiTracerSession.
- `def _get_clipper` — Return a GeminiClipper wired to the cached session, or None.
- `def is_warmed` — True once the PhiTracerSession has been built and the snapshot is ready.
- `def gemini_clip` — Clip the top-K most relevant tracks from the Liked Songs library for a query.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `engine.phi_session`

---

## Semantic links

→ [[2025-12-06-114407-gemini-clipper]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

## Related notes

→ [[source/engine-phi-session]]
→ [[source/mcp-server-tools-phi-dispatch]]
→ [[source/mcp-server-server]]
→ [[source/mcp-server-tools-system]]
→ [[source/mcp-server-hooks]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-search]]

---

## Semantic links

→ [[mcp-server-tools-phi-clip]]
→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
