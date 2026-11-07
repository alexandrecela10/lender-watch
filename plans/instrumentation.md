# Plan: usage and quality instrumentation

Date: 2026-11-07. Owner: Alexandre. Build: day 3, one step per Claude Code session.
Source: `specs/instrumentation.md` (commit `057f508`), from `intent/instrumentation.md` (commit `9bddf51`).
Evidence: the repo's code and one offline evaluation. No LP analyst has been interviewed. The analyst-side pain is inferred.

Scope: the spec's sections 1 to 3 and its "Concerns and resolutions" table. No change to matching, flags or returned values. Every step ends with `make test` and `make lint` green, and a commit.

## Files that change

| File | New or changed | What changes |
|---|---|---|
| `erm/telemetry.py` | New | `configure()`, `run(source)` context manager, request id in a `ContextVar`, anonymous session id, JSON formatter with the field allowlist, `count(status, flag_level)`, `run_metrics` writer for `data/metrics.sqlite`, Langfuse client factory |
| `erm/match/judge.py` | Changed | Price table per model with source and date, `cost_usd(model, usage)` |
| `erm/api.py` | Changed | `_decide` keeps `message.usage`, times the call, logs `judge_call` or `judge_error`, sends one trace, adds to the run's judge counters. `enrich_table` calls `telemetry.count` per row |
| `erm/cli.py` | Changed | `configure()`, wraps `enrich` in `run(source="cli")` |
| `erm/mcp_server.py` | Changed | `configure()` to stderr, wraps each tool in `run(source="mcp")` |
| `app/review.py` | Changed | `configure()`, wraps `run()` in `run(source="app")` and `answer()` in `run(source="app_answer")`, one session id per Streamlit session |
| `.gitignore` | Changed | Add `data/metrics.sqlite` |
| `tests/test_telemetry.py` | New | Acceptance checks 1 to 8 from the spec |

`tests/` and `CLAUDE.md` are also touched by M7. Merge M7 before day 3 starts so the two never edit the same files at once.

## Order

### I1. Telemetry core, no wiring

Files: `erm/telemetry.py`, `tests/test_telemetry.py`, `.gitignore`.
Build the formatter, allowlist, request id, `run()` and the `run_metrics` table. Nothing calls it yet, so product behaviour can't change.

Exit criteria
- `uv run pytest tests/test_telemetry.py -k "allowlist or request_id or metrics_write"` passes: spec checks 2, 3 and 8 (metrics part).
- `make test` and `make lint` green.
- Commit: `feat(telemetry): JSON logs, request id, run_metrics table`.

### I2. Judge cost and local judge logs

Files: `erm/match/judge.py`, `erm/api.py`, `tests/test_telemetry.py`.
Load the `claude-api` skill and take prices for `claude-opus-5-5` from Anthropic's pricing page. Write the page and date next to the table (resolution 10). `_decide` stops discarding usage.

Exit criteria
- `uv run pytest tests/test_telemetry.py -k judge_call` passes: with a fake client, 1 unclear pair gives 1 `judge_call` line with `verdict`, tokens, `cost_usd` and `latency_ms` (spec check 4, local part).
- `uv run pytest tests/test_telemetry.py -k unknown_model` passes: a model missing from the table logs `cost_usd: null`.
- `make evals` still prints `PASS` with precision 1.000 and recall 0.936.
- Commit: `feat(telemetry): judge cost and latency in logs`.

### I3. Langfuse traces on judge calls (riskiest)

Files: `erm/telemetry.py`, `erm/api.py`, `tests/test_telemetry.py`.
First read the installed Langfuse SDK (5.1.0 in `uv.lock`) and note in the commit message: the option that turns tracing off, how to set input and output explicitly, and whether it exports spans other than its own. Use explicit observations only. No `@observe` decorator, because it captures function arguments, and the arguments are company names.

Exit criteria
- `uv run pytest tests/test_telemetry.py -k trace_payload` passes: the recorded trace payload, serialised, contains none of the listed name, sector, owner, borrower text, `pair_id` or `entity_id` (spec check 5).
- `uv run pytest tests/test_telemetry.py -k no_langfuse_when_judge_off` passes for CLI, app and MCP entry points (spec check 6).
- `uv run pytest tests/test_telemetry.py -k trace_send_failed` passes: a failing trace send leaves results unchanged (spec check 8, trace part).
- Commit: `feat(telemetry): Langfuse traces on judge calls, no names`.

### I4. Wire the three entry points

Files: `erm/cli.py`, `erm/mcp_server.py`, `app/review.py`, `erm/api.py`, `tests/test_telemetry.py`.

Exit criteria
- `uv run pytest tests/test_telemetry.py -k "enrich_counts or mcp_stdout"` passes: spec checks 1 and 7.
- `make test` passes, including the existing person-answer tests in `tests/test_api.py` (spec check 9).
- Demo run, judge off, from the repo root:
  - `uv run python -m erm.cli enrich data/demo/sample_list.csv --name-column Company --sector-column Sector --sponsor-column Owner --out /tmp/v.xlsx 2> /tmp/v.log`
  - `sqlite3 data/metrics.sqlite "select source, names_in, names_matched, names_needing_review, flagged, worth_a_look, judge_calls from run_metrics order by started_at desc limit 1"` shows `cli`, `names_in` equal to the rows in the CSV, and `judge_calls` 0.
  - `uv run python -c "import json; print(len({json.loads(l)['request_id'] for l in open('/tmp/v.log')}))"` prints `1`.
  - `uv run python -c "import pandas as pd; log = open('/tmp/v.log').read(); print(sum(n in log for n in pd.read_csv('data/demo/sample_list.csv').Company))"` prints `0`.
- `make run`, click "Check lender filings" on the sample list, then answer one match. Two new `run_metrics` rows: `app` and `app_answer`.
- Commit: `feat(telemetry): instrument CLI, app and MCP runs`.

### I5. Verify

Run the `verifier` agent. It runs `make test`, `make lint`, `make evals` and the demo enrich, and reports only.
A live judge-on run with real Langfuse keys sends names to Anthropic. It needs Alexandre's approval first, uses `data/demo/sample_list.csv` only, and ends with a look at one trace in the Langfuse UI to confirm its input holds only `has_sector`, `has_owner` and `n_examples`.

## Risks

| Risk | What it would break | Mitigation |
|---|---|---|
| Langfuse SDK captures more than we set: function arguments, or other OpenTelemetry spans in the process | Company names reach a third party | I3 reads the SDK first, uses no decorator, and the trace-payload test asserts on the serialised payload |
| A log line on stdout in the MCP server | The calling agent's protocol breaks | `configure()` attaches to stderr only; spec check 7 runs the server and reads stdout |
| Streamlit's `st.rerun()` raises inside `answer()` | `run()` records a normal rerun as `status: error` | `run()` treats Streamlit's rerun and stop exceptions as `ok`; covered in I4 |
| Price table wrong or stale | Cost reads wrong with no warning | Price comes from the pricing page with its date; unknown model logs null |
| Hosted app disk is read-only or resets | `run_metrics` rows lost on the demo | Write failure logs `metrics_write_failed` and never fails the run; `run_finished` repeats every count |
| Counting twice: `gather_facts` calls `resolve_entity` | Inflated `names_in` | Runs open and count at entry points only, never inside the engine |
| A new field added later carries a name | A leak in logs | The allowlist drops unknown fields; spec check 3 covers it |

**Riskiest step: I3.** It's the only step that sends anything off the machine, and its safety depends on SDK behaviour we haven't read yet. Everything else fails locally and visibly. I3 can fail silently by sending more than it shows.

## What this plan does not do

- Drift thresholds. Needs one quarter of runs.
- Named users. Needs a login, which is a separate decision.
- Durable storage for hosted-app run records.
- The private-mode shared-engine bug in `app/review.py` (spec resolution 12). Separate follow-up.

## Kickoff prompt for each build step (day 3)

```
Read CLAUDE.md, specs/instrumentation.md and plans/instrumentation.md.
Implement step I<n> only. Stop when its exit criteria are met, paste the evidence, and wait.
```
