# Entity Reconciliation Machine

**Product:** an entity reconciliation engine for private capital. It links the same company across sources that name it differently, and returns facts with a link to the source row. First use: LP analysts see lender-side stress (BDC loan marks) on the companies inside their PE funds.

**Brief and decisions:** `outputs/opportunity-analyses/`, then `outputs/prds/`. Earlier drafts: `docs/archive/PRD_1.md`, `docs/archive/CLAUDE_1.md` (context only, not binding).

**Hard constraints**
- Public data only (SEC EDGAR, SEC BDC data sets, sponsor websites). No employer, client or counterparty data. Never name an organisation Alexandre is applying to; company names from public sources are fine.
- Every fact keeps its source (filing URL + row). No uncited value is ever shown.
- Pain is inferred from public signals until real LP users are interviewed. Say so in every document.
- Core engine stays source-agnostic so other side projects and customers can plug in their own lists and sources.
- SEC access: declared User-Agent, max 5 requests/second, cache every download under `data/raw/` (git-ignored).
- Keys live in `.env`. Never print or commit them.

**Stack:** Python 3.12 via `uv`. Engine in `erm/`, app in `app/`, measurement in `eval/`, data in `data/`. See `README.md`.

## Commands

Run from the repo root. Healthy output in brackets.
- `make test`: runs `uv run pytest` [`51 passed`, about 45 seconds; the first run on a machine adds about 100 seconds to build the app's search index]
- `make lint`: runs `ruff check` and `ruff format --check` [`All checks passed!` then `N files already formatted`; any `Would reformat` line is a failure]
- `make evals`: offline eval gate, `uv run python -m eval.offline`, thresholds in `evals/thresholds.yaml` [`precision 1.000`, `recall 0.936`, `PASS`]. It replays saved name-search hits and judge verdicts, so it only re-tests the exact-name rule live.
- `make run`: the review app, `uv run streamlit run app/review.py` [Streamlit prints a local URL]
- `make mcp`: the tool server for AI agents, `uv run python -m erm.mcp_server` [no output; it serves over stdin and exits when stdin closes]
- `uv run python -m eval.plan_drift plans/<plan>.md <step>`: run right after each build step's commit, then amend the commit with the log; lists files changed outside the step's plan and appends a row to `plans/<plan>-drift.md` [one row, `none` when the build matches the plan]
- `make hooks`: run once after cloning: installs the git pre-commit key scan [`pre-commit key scan installed`]

## Verifying your work

- Run `make test` and `make lint` before reporting any task done. Paste their output in the report.
- When a test fails, fix the code, not the test.
- Never skip, mark as expected to fail, or delete a failing test.
- For any change under `app/`, also run the verifier's browser step (`.claude/agents/verifier.md` step 6). It checks screenshots against `specs/review-app-acceptance.md`.

## Things Claude gets wrong

Data rules learned the hard way:
- In SEC's `soi.tsv`, use `ddate` as the period. About half the rows are prior-period comparison schedules.
- Check any column or claim against a real filing before relying on it.
- All labels so far are Claude's. Never describe them as human or hand-labelled.
- Principal can be in local currency while cost and value are in US dollars. There is no currency tag.
- Flags use the size-weighted average. A single small position never flags a company.
