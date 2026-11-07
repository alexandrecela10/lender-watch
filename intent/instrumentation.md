# Intent: usage and quality instrumentation for every run

Author: Alexandre Cela, writing as the person who runs and maintains the engine. Status: draft, awaiting correction by the author.
Source: no opportunity analysis. This comes from `plans/sdlc-day2.md` M8, and Stage 6 (monitoring) and the value gate depend on it.
Evidence: the repo's code and one offline evaluation run. No LP analyst has been interviewed. The analyst-side pain is inferred.

## Problem

- After a list runs, nothing is kept.
- So we can't tell how often the engine is used, how many names need a person, or what the AI judge costs.
- We can't see matching get worse until someone spots a wrong loan by hand.
- Our only numbers come from one offline test: 3 of 84 companies needed a person, and the judge cost $0.40 per 100 names (`outputs/analyses/matching-comparison.md`).

## Proposed outcome

- Every run leaves a record I can read after it ends.
- For each run: where it came from (the app, the command line or an AI agent), names in, names matched, names needing a person, names flagged, and time taken.
- For each AI judge call: its cost, its time and its answer.
- Each run gets one tracking number, so all its records can be found together.

What should change:
- Runs with a usage record: from 0% today (observed: no logging exists) to 100%.
- Judge calls with a cost and latency record: from 0% (observed: usage is discarded) to 100%.
- Share of names needing a person, per run: today unobserved for live runs. Offline baseline 3 of 84 companies. Target: tracked every run, so a rise is visible within one run.
- Live judge cost per 100 names: unobserved. Offline batch baseline $0.40. Target: measured, not estimated.

What must not get worse:
- Company names, uploaded lists, keys or prompt bodies in any log or trace: 0.
- Values shown without a filing link: 0.
- Names sent to a third party with the judge off: 0.
- `make test`, `make lint` and `make evals` stay green.

## Affected users and systems

Users: Alexandre now, as the operator. Later, whoever runs the value gate and the monitoring stage. LP analysts are affected only indirectly: they should never see this.
Systems: `erm/api.py` (the Engine, where runs start and the judge is called), `erm/match/judge.py`, `erm/cli.py`, `erm/mcp_server.py`, `app/review.py`, `erm/store.py` (the SQLite store), Langfuse (an outside tracing service; keys already in `.env`).

## Constraints

- Never log a company list, a company name from an uploaded list, a key, or a prompt or response body. Log counts and ids (`api-and-logging` rule 2).
- Logs are JSON, one object per line, with a request id, using the standard `logging` module (`api-and-logging` rule 1).
- The judge stays off by default. Turning on instrumentation must not turn on any new outside call that carries company names (`data-handling` check 3).
- Langfuse is a third party. No company name, prompt or reply goes there, with the judge on or off (spec concern 1).
- Keys live in `.env`. Never printed, logged or committed.
- A person's saved answer still overrides every automated answer. Instrumentation reads decisions; it never changes them.
- Every new public function ships with a test.

## Open questions

- "Who ran a list": the public app has no login. Is a run source (app, command line, MCP) plus an anonymous session id enough? If the value gate needs named users, we need a login first, and that's a separate decision.
- What counts as drift? Candidates: share of names needing review, share matched, judge "unsure" rate. Each needs one quarter of runs before a threshold means anything. Unobserved.
- Where do public app visitors' run records go? The hosted app copies the decision store per visitor into a temporary folder, so a local table there is lost when the session ends.
