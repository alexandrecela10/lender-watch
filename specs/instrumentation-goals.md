# Goals: specs/instrumentation.md

Passing bar: all 7 criteria true.

1. Every concern in the spec names the rules in tension and one proposed resolution.
2. The spec states what is sent to Langfuse as a complete list, and what is never sent.
3. Each `run_metrics` column has a type and a one-line definition traceable to `Resolution.status` or `Flags.level`.
4. The run boundary is defined for each of CLI, app and MCP.
5. Each acceptance check is binary and names its test file or command.
6. The document contains 0 em dashes.
7. Every concern has a row in "Concerns and resolutions" naming who raised it, the decision and why, before `plans/instrumentation.md` is drafted.
