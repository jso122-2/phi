# scripts / samba_mcp_server.py

#source #python

> path: scripts/samba_mcp_server.py  
> ext: .py  

---

# scripts / samba_mcp_server.py


Samba GNN — MCP Server
Proper JSON-RPC 2.0 MCP server using FastMCP.
Registers with Cursor via .cursor/mcp.json and exposes the Obsidian graph
orchestration tools as native MCP tools.

Usage (Cursor handles this automatically via .cursor/mcp.json):
    python mcp_server.py

    # With a specific checkpoint:
    python mcp_server.py --checkpoint checkpoints/best.pt

    # To test tools manually:
    python mcp_server.py --dev

The server loads the model lazily on first tool call and caches it.
If no checkpoint exists yet, tools return a helpful "not trained" message
rather than crashing.

Tool

Defines: _find_best_checkpoint, _get_orchestrator, _not_trained_msg, _fmt, samba_find_related, samba_suggest_links, samba_route_query, samba_get_clusters, samba_graph_stats, samba_euler_spectrum, samba_refresh, samba_apply_links, samba_create_bridge, samba_coherence_report, samba_record_coherence, samba_write_note, samba_annotate, samba_song_derivatives, samba_cluster_derivatives, samba_forecast_chi, samba_spotify_enrich, _get_cairrn, samba_cairrn_z_report, samba_cairrn_z_inject, _get_mycelial, samba_mycelial_spore, samba_mycelial_trace, samba_mycelial_state, samba_mycelial_decay, samba_mycelial_propagate, samba_mycelial_anastomoses, samba_mycelial_apply_anastomoses, cairrn_hub_state, cairrn_inject, main, _top_note, _Snap, _sort_key, __init__, index_of

---

## Semantic links

→ [[scripts-samba-mcp-server]]
→ [[scripts-mcp-bridge]]
→ [[mcp-server-server]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[mcp-server-tools-graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-samba-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-mcp-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-server-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
