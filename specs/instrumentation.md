# Spec: usage and quality instrumentation

Source: `intent/instrumentation.md`. Status: draft, 2026-11-07. Concerns resolved in "Concerns and resolutions" below, pending Alexandre's review. Ready for `plans/instrumentation.md`.
Evidence: the repo's code and one offline evaluation. No LP analyst has been interviewed, so the analyst-side pain is inferred.

## Bottom line

- Every run of a list leaves a short record: where it came from, names in, names matched, names needing a person, and time taken.
- Each AI judge call also records its cost and time.
- That judge record also goes to Langfuse, an outside monitoring service.
- No company name leaves your machine through this, even with the judge on.
- That is stricter than the original brief; concern 1 explains why.

## Concerns and resolutions

One row per concern. "Fresh pass" means the separate spec process raised it. "M8 session" means the session that resolved the spec added it. Decided by the M8 session on 2026-11-07, pending Alexandre's review.

| # | Concern | Raised by | Decision | Why |
|---|---|---|---|---|
| 1 | Names could reach Langfuse with the judge on. Intent line 26 (0 names in any trace) contradicts intent line 41 (names allowed with consent). The scope's "judge off" condition protects nothing. | Fresh pass | No company name, prompt, reply or reason goes to Langfuse, judge on or off. This overrides intent line 41. | Consent to the judge is consent to Anthropic only. Cost, latency and verdict need no names. |
| 2 | `ERM_USE_JUDGE` is only one of three judge switches (CLI flag, app checkbox, MCP env var). | Fresh pass | "Judge on" means `engine.client is not None` at call time. | One rule covers all three entry points. A rule on the env var would miss two. |
| 3 | `pair_id` and `entity_id` are short hashes of names. Anyone with a candidate list can reverse them. | Fresh pass | Neither id goes to Langfuse or to any log line. `pair_id` is removed from the log allowlist (see row 9). | The fresh pass allowed `pair_id` in local logs. Row 9 shows local logs are not always local. |
| 4 | Log lines on stdout would break the MCP server's protocol. | Fresh pass | All logs go to stderr. The CLI keeps its one summary line on stdout. | MCP serves over stdin and stdout. One stray line breaks the calling agent. |
| 5 | The public app copies the decision store per visitor into a temp folder, so run records there are lost. | Fresh pass | `run_metrics` lives in `data/metrics.sqlite`, separate from the decision store. Durable hosted storage is not tackled. | Keeps run records out of the per-visitor copy. The hosted disk still resets on restart; that is accepted for now. |
| 6 | Langfuse keys already sit in `.env`, so starting Langfuse whenever keys exist would add an outside call that is on by default. | Fresh pass | Langfuse starts only when the judge is on and both Langfuse keys are set. | `data-handling` check 3 forbids a new outside call that is on by default. |
| 7 | File names and exception messages can carry fund or company names. | Fresh pass | No paths and no exception messages in logs. Exception type only. | A file named after a fund names the fund. A pandas `KeyError` repeats the value it failed on. |
| 8 | The judge's `reason` quotes the filing row, which names the borrower. | Fresh pass | Logs and traces carry the verdict word only. | `api-and-logging` rule 2 forbids response bodies. |
| 9 | The hosted demo runs on Streamlit Community Cloud (`README.md`). Its stderr is collected by the host, so "local logs" there go to a third party. | M8 session | The allowlist holds no name-derived field at all. `person_answer` lines carry `decided_by` and `verdict` only. | The same log code runs locally and hosted. Only a rule that is safe on the host is safe. |
| 10 | Cost needs a price per token. The spec does not state one, and an assumed price would be an invented number. | M8 session | The build reads prices from Anthropic's pricing page through the `claude-api` skill and cites the page and date next to the table. A model missing from the table logs `cost_usd: null`. | CLAUDE.md and the intent forbid invented numbers. A null cost is visible; a wrong one is not. |
| 11 | Judge cost per run is only in Langfuse, which is off when its keys are missing. The intent's metric "live judge cost per 100 names" would then be unmeasurable. | Fresh pass (as an open question) | Add `judge_calls` and `judge_cost_usd` to `run_metrics`. | Makes cost per 100 names one local query and keeps it when Langfuse is down. Counts and dollars only, no names. |
| 12 | Private-mode app shares one cached `Engine` across tabs and sets `engine.client` per click. | Fresh pass (found, not fixed) | Not tackled in this feature. Logged as a follow-up. | It's a concurrency bug in the app, not an instrumentation rule. Instrumentation records the setting each call actually used. |

## Problems this solves

| Problem | Today | Hypothesis (if/then/because) | Success metric (target) | Expected impact |
|---|---|---|---|---|
| Runs leave no record | 0% of runs recorded (observed: no `logging` call in `erm/` or `app/`) | If each entry point opens a run with a request id, then every run is recorded, because the only paths in are CLI, app and MCP | Runs with a `run_metrics` row and a `run_finished` log line: 100% | The operator can count runs by source. Analyst usage stays unobserved until a login exists |
| Judge cost and latency are thrown away | 0% of judge calls recorded (observed: `v, _usage = ...` in `erm/api.py`) | If the call site keeps `message.usage` and times the call, then every live call has a cost, because usage comes back on every reply | Live judge calls with a Langfuse trace and a `judge_call` log line: 100% | Live cost per 100 names becomes measured. Offline batch baseline is $0.40; live value unobserved |
| Review load per run is invisible | Unobserved for live runs. Offline baseline: 3 of 84 companies sent to a person | If every run stores names in and names needing review, then a rise shows up on the next run, because the share is computed per row | Runs with `names_needing_review` filled: 100% | A rise in review share is visible within one run instead of when someone spots a wrong loan |

**Must not get worse:** 0 company names, uploaded lists, file paths, keys or prompt and response bodies in any log line, `run_metrics` row or trace. `make test`, `make lint` and `make evals` stay green. A person's saved answer still wins.

**Not tackled:**
- Drift thresholds. Missing: one quarter of runs before any threshold means anything.
- Named users. Missing: a login, which is a separate decision.
- Durable hosted run records. Missing: a storage choice for the hosted app.
- Traces on the offline batch judge in `eval/run_judge_batch.py`. Missing: a need; the batch API already reports cost.

## 1. Request id and JSON logs

**What it is.** A new module, `erm/telemetry.py`, gives each run one request id and formats every log line as one JSON object. It uses the standard `logging` module.

**Run boundary.** One run is one list or one agent call:
- CLI: one `enrich` command.
- App: one click on "Check lender filings". A person's answer in the review tab is its own short run (`source="app_answer"`).
- MCP: one tool call (`resolve_entity`, `gather_facts` or `review`).

`gather_facts` calls `resolve_entity` inside it. Runs open at the entry points only, so one call never counts twice.

**How the id travels.** `telemetry.run(source=...)` is a context manager. It sets a random `request_id` (UUID4) in a `contextvars.ContextVar`. Every log line inside the block picks it up. On exit it writes the `run_metrics` row and the `run_finished` line, also when the run raised.

**Format.** One line per event on stderr:

```json
{"ts":"2026-11-07T10:15:02Z","level":"INFO","event":"run_finished","request_id":"6f1c...","source":"cli","judge_on":false,"names_in":240,"names_matched":180,"names_needing_review":12,"flagged":9,"worth_a_look":14,"duration_ms":81234,"status":"ok"}
```

**Events.** `run_started`, `run_finished`, `judge_call`, `judge_error`, `person_answer`, `metrics_write_failed`, `trace_send_failed`.

**Field allowlist.** The formatter writes only these keys and drops any other: `ts`, `level`, `event`, `request_id`, `session_id`, `source`, `judge_on`, `status`, `error_type`, the five run counts, `duration_ms`, `latency_ms`, `verdict`, `decided_by`, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `judge_calls`, `judge_cost_usd`. No name-derived id is on the list (resolution 9). An allowlist fails safe: a future `extra={"name": ...}` is dropped, not logged.

**Setup.** Library code in `erm/` gets a logger and never configures handlers. `erm/cli.py`, `erm/mcp_server.py` and `app/review.py` call `telemetry.configure()` once. Level comes from `ERM_LOG_LEVEL`, default `INFO`.

**Session id.** "Who ran it" is answered with `source` plus an anonymous `session_id`: one random UUID per CLI process, MCP server process or Streamlit session. No user identity.

## 2. The `run_metrics` table

**What it is.** One row per run in `data/metrics.sqlite`, a SQLite file separate from `data/decisions.sqlite`. The path is an argument, so tests use a temp folder.

| Column | Type | Meaning |
|---|---|---|
| `request_id` | TEXT, primary key | Same id as every log line of the run |
| `session_id` | TEXT | Anonymous id from section 1 |
| `source` | TEXT | `cli`, `app`, `app_answer` or `mcp` |
| `started_at` | TEXT | UTC, ISO 8601, seconds |
| `judge_on` | INTEGER | 1 if a judge client was set at run start |
| `status` | TEXT | `ok` or `error` |
| `names_in` | INTEGER | Rows in the list, duplicates included |
| `names_matched` | INTEGER | Names whose resolution status is `matched` |
| `names_needing_review` | INTEGER | Names whose status is `needs_review` (at least one unsure candidate) |
| `flagged` | INTEGER | Names with flag level `flagged` |
| `worth_a_look` | INTEGER | Names with flag level `worth_a_look` |
| `duration_ms` | INTEGER | Wall time of the run |
| `judge_calls` | INTEGER | Live judge calls in the run, 0 with the judge off (resolution 11) |
| `judge_cost_usd` | REAL | Sum of `cost_usd` for those calls; null if any call had no price (resolution 10) |

The scope asked for "flags". The engine has two flag levels, so the table keeps both. One column would hide whether a rise came from serious or mild cases.

**Example and its counterfactual.** A CLI list of 3 names, judge off: Ascensus resolves by exact name, Orion Group has one unclear candidate, Foundation finds nothing. The row reads `names_in 3, names_matched 1, names_needing_review 1`, with no `judge_call` line. Had the judge been on and answered `match` for Orion Group, the row would read `names_matched 2, names_needing_review 0`, and one `judge_call` line and one trace would exist.

**Rules.** The table holds counts only, never a name, pair id or path. It reads decisions and never writes them. A failed write logs `metrics_write_failed` and never fails the run.

## 3. Langfuse traces on judge calls

**When.** Only for a live call to `judge_mod.judge` in `Engine._decide`. A saved verdict reused from the store is not a call and gets no trace. The Langfuse client exists only when `engine.client is not None` and `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are both set. With either key missing, judge calls still log locally.

**What is sent, complete list.**
- Observation type `generation`, name `judge_call`.
- `model`: `message.model` from the reply, not the `MODEL` constant. The call uses server-side fallback, so the model that answered can differ.
- Usage: input, output, cache read and cache write tokens from `message.usage`.
- Cost in US dollars, computed locally and sent explicitly, so local logs and Langfuse show the same number.
- Latency, from the observation's start and end.
- Input: `{"has_sector": bool, "has_owner": bool, "n_examples": int}`.
- Output: `{"verdict": "match" | "no_match" | "unsure", "stop_reason": str}`.
- Metadata: `request_id`, `source`, `prompt_version` (first 8 characters of a hash of `SYSTEM`).

**Never sent.** Company name, sector, owner, borrower text, filing rows, the prompt, the reply, the reason, `pair_id`, `entity_id`, `mention_key`, file paths, keys.

**Cost.** A price table per model, with the date and Anthropic's pricing page as its source, lives next to `MODEL` in `erm/match/judge.py`. A model missing from the table logs `cost_usd: null`. The offline $0.40 per 100 names was at batch prices. Live calls aren't batched, so the live figure will differ. No live number is assumed here.

**Failures.** An `anthropic.APIError` logs `judge_error` with `error_type` and `latency_ms`, sends a trace with `status: error`, and keeps today's behaviour: the pair is saved as unsure and asked again next run. A Langfuse failure logs `trace_send_failed` and never fails a run. Each run calls `flush()` on exit so a short CLI run doesn't drop its traces.

## Acceptance checks

Each is a test in `tests/test_telemetry.py` unless marked.
1. A run through `Engine.enrich_table` on a 3-row fixture writes 1 `run_metrics` row whose counts match the fixture.
2. Every log line of that run parses as JSON and carries the same `request_id`.
3. A log call with `extra={"name": "Orion Group"}` produces a line without `Orion Group`. No log line of the run contains a `pair_id` or `entity_id` value.
4. With a fake judge client, 1 unclear pair produces 1 `judge_call` line with `verdict`, tokens, `cost_usd` and `latency_ms`, and 1 recorded trace payload.
5. The recorded trace payload, serialised, contains none of: the listed name, sector, owner, borrower text, `pair_id`.
6. With `client=None`, no Langfuse client is created (checked with a stub), for CLI, app and MCP entry points.
7. With the MCP server, stdout carries protocol messages only; logs appear on stderr.
8. A failed metrics write and a failed trace send each leave the run's results unchanged.
9. A person's saved answer is unchanged after an instrumented run (existing test still passes).
10. `make test`, `make lint` and `make evals` pass.
