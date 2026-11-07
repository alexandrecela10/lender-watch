# Plan: SDLC day 1, controls around the existing engine

Date: 2026-11-07. Owner: Alexandre. Reviewer: product owner session (chat).
Follows the AI-native SDLC playbook (Anthropic, Sept 2026), adapted for one person: roles are separated by committed artifacts and by agents, not by people.

Scope today: no product behaviour changes. Only the files the playbook's Build and Test stages need. Each milestone ends with evidence and a commit. One milestone per Claude Code session.

## M1. Skeleton and source of truth

Files that change
- New: `intent/` (holds `lp-credit-readthrough.md`), `specs/.gitkeep`, `plans/` (holds this file), `evals/.gitkeep`, `.claude/skills/.gitkeep`, `.claude/agents/.gitkeep`, `.claude/hooks/.gitkeep`, `Makefile`.
- `.gitignore`: remove `CLAUDE.md`. Keep `context-library/` and `PRD_1.md`, `CLAUDE_1.md`, `KICKOFF_PROMPTS.md` ignored, moved under `docs/archive/`.
- `Makefile` targets: `test` (`uv run pytest`), `lint` (`uv run ruff check . && uv run ruff format --check .`), `evals` (stub: `python -m eval.offline`, exits 1 until M4), `run` (`uv run streamlit run app/review.py`), `mcp`.

Exit criteria
- `make test` and `make lint` run and print a result. Record the healthy output.
- `git status` shows `CLAUDE.md` tracked.
- Commit message: `chore(sdlc): skeleton, Makefile, CLAUDE.md tracked`.

Risk: `ruff format --check` may fail on existing files. Fix formatting in its own commit, no logic changes.

## M2. CLAUDE.md under a page

Files that change: `CLAUDE.md`.

Keep the current content. Add two sections in the playbook's shape:
- `## Commands`: each `make` target with one line of healthy output copied from M1.
- `## Verifying your work`: run `make test` and `make lint` before reporting any task done, paste the output, fix the code not the test, never skip or delete a failing test.
- `## Things Claude gets wrong`: start with the five "data rules learned the hard way" already in the file, one line each.

Exit criteria
- `wc -l CLAUDE.md` under 70 lines.
- A fresh Claude Code session asked "how do I run the tests" answers from CLAUDE.md without reading other files.
- Commit: `docs(sdlc): CLAUDE.md commands and verification block`.

## M3. Three skills in the repo

Files that change: `.claude/skills/data-handling/SKILL.md`, `.claude/skills/api-and-logging/SKILL.md`, `.claude/skills/intent-md/SKILL.md`.

Each SKILL.md: frontmatter `name` and `description` (when it triggers), then a numbered body of what to do.

- `data-handling`: triggers on any change touching `data/`, `erm/connectors/`, fixtures, demo text, or anything that sends data to an external API. Body: the six constraints from `intent/lp-credit-readthrough.md` as checks, plus "state in the summary which check applied".
- `api-and-logging`: triggers on any change to `erm/api.py`, `erm/mcp_server.py`, `app/`, or any new function called by a user or an agent. Body: JSON logs with a request id; never log a company list, a key or a prompt body; every public function has a test in `tests/`; every value returned carries `url` and `locator`.
- `intent-md`: triggers on "write an intent", "new idea", "new use case", or a `/pm-os:opportunity-analysis` output. Body: write `intent/<slug>.md` with the sections Problem, Proposed outcome (with what changes and what must not get worse), Affected users and systems, Constraints, Open questions. Pull from the opportunity analysis when one exists. Never invent a number; mark it unobserved.

Exit criteria
- Each skill triggers when the task is phrased three different ways. Log the three phrasings and the result in `outputs/skill-test-results/sdlc-day1.md`.
- Commit: `feat(sdlc): data-handling, api-and-logging, intent-md skills`.

## M4. Offline evals as a gate

Files that change: `eval/offline.py` (new), `evals/thresholds.yaml` (new), `Makefile` (`evals` target), `tests/test_offline_eval.py` (new).

- `eval/offline.py` replays `data/eval/judge_results.csv` and the exact-name rule against `data/eval/answer_key.csv`, computes pair precision and recall for method `e_exact_name_rule_then_judge`, and exits 1 if below `evals/thresholds.yaml` (start: pair precision 0.97, recall 0.90, both below the observed 1.00 and 0.936 so the gate has room). No network, no API key.
- The test checks the script exits 0 on the current data and 1 on a copy with 5% of labels flipped.

Exit criteria
- `make evals` prints precision, recall, threshold, PASS. Record the output.
- `make test` includes the new test.
- Commit: `feat(sdlc): offline eval gate on the answer key`.

Risk: `judge_results.csv` columns may not map one to one onto `answer_key.csv`. Read `eval/compare.py` first; it already joins them.

## M5. Build hooks and a verifier agent

Files that change: `.claude/settings.json`, `.claude/hooks/protect-paths.sh`, `.claude/hooks/no-secrets.sh`, `.claude/hooks/lint-on-edit.sh`, `.claude/agents/verifier.md`.

- `protect-paths.sh` (PreToolUse on Edit and Write): block edits under `data/raw/`, `data/eval/answer_key.csv`, `data/eval/judge_results.csv`, and `tests/` when the env var `ERM_FIX_TASK=1` is set. Exit 2 with a one-line reason and the route to approval.
- `no-secrets.sh` (PreToolUse on Bash matching `git commit`): grep the staged diff for `sk-ant-`, `ANTHROPIC_API_KEY=`, `SEC_USER_AGENT=` with a value. Exit 2 on a hit.
- `lint-on-edit.sh` (PostToolUse on Edit and Write of `*.py`): `uv run ruff format <file>` then `uv run ruff check <file>`.
- `verifier.md`: tools Bash and Read. Runs `make test`, `make lint`, `make evals`, then `uv run python -m erm.cli enrich data/demo/sample_list.csv --name-column Company --sector-column Sector --sponsor-column Owner --out /tmp/v.xlsx` and reports row counts. Reports only. Does not fix.

Exit criteria
- Ask Claude Code to edit `data/eval/answer_key.csv`. The hook blocks it and the reason appears.
- Stage a fake key in a scratch file and try to commit. The hook blocks it.
- Run the verifier agent. It reports all three make targets and the enrich row count.
- Commit: `feat(sdlc): build hooks and verifier agent`.

## Order and parallelism

M1 → M2 → M3 and M4 in parallel (worktrees `sdlc-skills` and `sdlc-evals`, they touch different files) → M5.

## Kickoff prompt for Claude Code (plan mode)

```
Read CLAUDE.md, intent/lp-credit-readthrough.md and plans/sdlc-day1.md.
Produce an implementation plan for milestone M1 only: the files that change,
the order, and the command that proves each exit criterion. Tell me what the
change could break and which step is riskiest. Don't write code until I accept.
```

Then for each later milestone: `Implement M<n> from plans/sdlc-day1.md. Stop when its exit criteria are met, paste the evidence, and wait.`

## Definition of done for the day

Five commits on `main` in the order above. `make test`, `make lint`, `make evals` all green from a clean checkout. The product owner session has reviewed each milestone against this file.
