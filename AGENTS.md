# Agent contract

Vault retrieval is an MCP tool call, not a shell one-liner.

## Search (required)

Call the **phi** MCP server:

- `find_query(query, mode="pericles")` — exact vault retrieval (Pericles funnel)
- `psspps_query(query, top_k=3)` — perspective-blended RAG

Do not run `python -c` / `psspps.find.run_find` / `run_psspps` ad hoc. The same bus tasks run in-process when the mmap worker is down.

Phi playback tools on the same server: `gemini_clip`, `phi_enqueue`, `phi_queue`.

## Cursor Cloud specific instructions

Cloud Agents do not inherit laptop `~/.cursor/mcp.json`. Attach stdio MCP **phi**:

| Field | Value |
|---|---|
| name | `phi` |
| command | `python3` |
| args | `["-m", "mcp_server.cloud"]` |
| env | `PYTHONPATH=/workspace`, `PYTHONUNBUFFERED=1` |

UI: [Cloud Agents MCP dropdown](https://cursor.com/agents). After attach, tools appear as the `phi` namespace (for example `phi-find_query`). If that namespace is missing, stop and tell the operator to add the server — do not fall back to ad-hoc Python.

Repo files: `.cursor/mcp.json` (stdio spec), `mcp_server/cloud.py` (entrypoint).
