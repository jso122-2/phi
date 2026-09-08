# /read — Inspect

#command #workflow #dispatcher

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- Bare `/read` loads vault context from this file and [[HOME]] / [[COMMANDS]]. No mutations.
- `/read <sub> …` dispatches a read-only MCP tool. Call `run_command` with the full slash. Do not use Shell.
- `/read help` lists every inspect subcommand.

Unknown `<sub>` is a topic, not an error — stay in workflow mode and explain that topic.

Primary inspect subs live in `mcp_server.commands.READ_SUBS` (status, health, index, graph, commands, …).
