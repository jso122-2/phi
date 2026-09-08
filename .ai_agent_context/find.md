---
name: find
description: >-
  Hybrid search. Searches Notion first via user-Notion MCP, then falls back
  to vault find_query. No agent spawn — direct tool dispatch.
---
# /find — Hybrid Search

This mode does NOT spawn a subagent. Execute the two-step search directly.

## Extract the query

Everything after `/find` in the raw command is the query string. If bare `/find` with no query — ask the user what to search for.

## Step 1 — Notion (primary)

Call `notion-search` from the `user-Notion` MCP namespace (OAuth-connected, no project token needed):

```
notion-search(query="<extracted query>")
```

- If results returned → show them (title, type, parent location). Show 5–10 most relevant.
- If Notion returns nothing or errors → proceed to Step 2.

## Step 2 — Vault fallback

Call `find_query` directly:

```
find_query(query="<extracted query>", mode="pericles")
```

- If results → show them (node slug, hub, score).
- If both steps return nothing → say so and suggest:
  - Alternate search terms
  - `run_command("/read traverse <related_term>")` for graph walking
  - `run_command("/read psspps <query>")` for RAG retrieval

## Result format

```
Notion
──────
• [Title] (page) — in: Parent / Database
• [Title] (database)

Vault
─────
• [node-slug]  hub: <hub>  score: <n>
```

Show Notion first, Vault second. Label each section.

## Rules

- Do not open, edit, or mutate any found page.
- Do not summarise found content unless the user asks.
- To read a Notion result: call `notion-fetch` with the page ID.
- To walk a vault result: call `run_command("/read traverse <slug>")`.
