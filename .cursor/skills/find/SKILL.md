---
name: find
description: Hybrid search for the phi project. Searches Notion first via user-Notion MCP, then falls back to vault find_query. No subagent spawn — direct dispatch. Use when the user types /find <query> or asks to search for pages, notes, or vault nodes.
---

# /find — Hybrid Search

Execute directly — no subagent.

## Step 1 — Notion (primary)

```
notion-search(query="<query>")   # user-Notion MCP namespace
```

Results → show title, type, parent. Show 5–10 most relevant.  
Nothing or error → Step 2.

## Step 2 — Vault fallback

```
find_query(query="<query>", mode="pericles")   # project-0-phi-spotify-rip
```

Both empty → suggest:
- Alternate search terms
- `run_command("/read traverse <related_term>")`
- `run_command("/read psspps <query>")`

## Output format

```
Notion
──────
• [Title] (page) — in: Parent / Database

Vault
─────
• [node-slug]  hub: <hub>  score: <n>
```

## Rules

- Do not open, edit, or mutate found pages.
- To read a Notion result: `notion-fetch` with the page ID.
- To walk a vault result: `run_command("/read traverse <slug>")`.
