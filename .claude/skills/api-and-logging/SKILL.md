---
name: api-and-logging
description: Rules for code people or AI agents call. Use before planning, describing or making any change to erm/api.py (the Engine), erm/mcp_server.py (the MCP tool server), app/ (the Streamlit review app), or any new public function, endpoint, CLI command or MCP tool. Also use for questions about logging, request ids, return shapes or test coverage of public functions.
---

# API and logging

1. **Log as JSON with a request id.** Each call made by a user or an agent gets one request id. Every log line for that call is one JSON object carrying it, plus the event name and timing. Use the standard `logging` module, not `print`.
2. **Never log sensitive content.** No company list, no company names from an uploaded list, no key or token, no prompt or response body sent to the AI judge. Log counts and ids instead, for example `{"request_id": "...", "event": "enrich", "rows": 240}`.
3. **Every public function has a test in `tests/`.** A new or changed public function, MCP tool or app action ships with a test in the same change. Run `make test` and paste the result.
4. **Every returned value carries its source.** Each fact returned to a user or agent includes the filing URL and the row it came from. In today's code these are `filing_url` and `filing_row` (the plan calls them `url` and `locator`). A value without both is not returned.
5. **Keep the engine source-agnostic.** Connector-specific logic stays in `erm/connectors/`. `erm/api.py` and the MCP tools take generic names and lists, so other sources can plug in.
6. If the change also touches data or sends anything to an external API, apply the `data-handling` skill too.
7. In your summary, state which of rules 1 to 5 applied and how each was met.
