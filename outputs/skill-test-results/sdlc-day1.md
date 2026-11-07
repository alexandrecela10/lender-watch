# Skill trigger tests, SDLC day 1 (M3)

Date: 2026-11-07. Branch: `claude/sdlc-skills-b90697`. Claude Code 2.1.317, model `claude-opus-5-5`.

**Result:** all 3 skills triggered on all 3 phrasings, first round. No description changes were needed, so there is no second round.

## Method

- Each phrasing ran in its own fresh process from the worktree root: `claude -p "<phrasing>" --output-format stream-json --verbose --max-turns 3 --disallowedTools "Edit,Write,NotebookEdit" < /dev/null`.
- No subagents. Each run has its own session id, so no context carried over from this session.
- Pass means the stream shows a `Skill` tool call with the expected skill name.
- Every phrasing asks for a plan or a description, not a change. `git status` after the runs showed only the new skill files.
- The init message of every run listed all 3 project skills as available.

## Round 1

| # | Phrasing | Expected | Invoked (in order) | Result |
|---|---|---|---|---|
| dh1 | I want to add a new connector in erm/connectors/ that loads sponsor portfolio pages. Describe the plan, don't change any files. | data-handling | data-handling | PASS |
| dh2 | Before I add a few sample companies to the demo fixtures, what rules do I need to follow? Just describe them, no edits. | data-handling | data-handling | PASS |
| dh3 | Outline how you would change the code so unclear company names get sent to the Anthropic API for a second opinion. Plan only, don't edit anything. | data-handling | data-handling, api-and-logging | PASS |
| al1 | Plan a new MCP tool in erm/mcp_server.py that lists every lender for a company. Describe the plan only, no edits. | api-and-logging | api-and-logging | PASS |
| al2 | How should I add logging to erm/api.py? Give me the plan, don't modify files. | api-and-logging | api-and-logging | PASS |
| al3 | I want a new button in the Streamlit review app that exports flagged loans. Describe what you'd build; don't change any files. | api-and-logging | api-and-logging, data-handling | PASS |
| im1 | Write an intent for a new idea: secondaries buyers screening a fund's holdings for lender stress. Show me the draft in chat, don't create files. | intent-md | intent-md | PASS |
| im2 | I have a new use case: credit teams watching their own borrowers. Describe what the intent file for it would contain. No edits. | intent-md | intent-md | PASS |
| im3 | Turn the opportunity analysis in outputs/opportunity-analyses/ into an intent. Show the plan only, don't write files. | intent-md | intent-md | PASS |

In all 9 runs the expected skill was the first tool call, before any file read.

dh3 and al3 also loaded the second skill. That is the intended overlap: sending names to Anthropic touches `erm/api.py`, and an export button returns data.

## Negative control

| Phrasing | Expected | Invoked | Result |
|---|---|---|---|
| How do I run the tests in this repo? Answer briefly, no edits. | none | none | PASS |

## Not tested

- Triggering during a real edit, rather than a planning request. The phrasings asked for plans so no files changed.
- Triggering when a task touches a file path without naming it. All 9 phrasings name the area or the action.
