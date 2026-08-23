# tests / test_mcp_wire.py

#source #python

> path: tests/test_mcp_wire.py  
> ext: .py  

---

# tests / test_mcp_wire.py


Direct MCP stdio protocol tests.

Speaks raw JSON-RPC 2.0 over stdin/stdout to the MCP server subprocess —
exactly as Cursor does when it spawns the server.  No mock, no import:
the server is a black box reached only through the wire protocol.

Run:
    pytest tests/test_mcp_direct.py -v

or directly:
    python tests/test_mcp_direct.py


Defines: MCPClient, test_initialize, test_tools_list, test_auto_init, test_init_check_contract, test_cairrn_hub_state, test_cairrn_hub_run, test_cairrn_hub_run_z_scoring, test_cairrn_hub_run_no_z, test_cairrn_batch_run, test_cairrn_batch_run_z_scoring, test_neg_exp_sharding_order, test_double_well_no_preinit, test_graph_status_init_free, client, test_mcp_initialize, test_mcp_tools_list, test_mcp_auto_init, test_mcp_init_check_contract, test_mcp_cairrn_hub_state, test_mcp_cairrn_hub_run, test_mcp_cairrn_hub_run_z, test_mcp_cairrn_hub_run_no_z, test_mcp_cairrn_batch_run, test_mcp_cairrn_batch_run_z, test_mcp_neg_exp_ordering, test_mcp_gated_no_preinit, test_mcp_graph_status_free, __init__, _send, _notify, _recv, call, tool, close

---

## Semantic links

→ [[scripts-samba-mcp-server]]
→ [[mcp-server-server]]
→ [[mcp-server-gate]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-main]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-main-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-samba-mcp-server-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-server-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
