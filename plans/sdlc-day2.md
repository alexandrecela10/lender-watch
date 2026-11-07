# Plan: SDLC day 2, close the gaps and give Claude eyes

Date: 2026-11-08. Owner: Alexandre. Reviewer: product owner session (chat).
Follows `plans/sdlc-day1.md` (M1 to M5 done, reviewed 2026-11-07).

## M6. Fix what the day-1 review found

Files that change: `.gitignore`, `Makefile`, `.claude/hooks/protect-paths.sh`, `.claude/hooks/no-secrets.sh`, `.claude/hooks/lint-on-edit.sh`.

1. Remove the two finished worktrees (`git worktree remove .claude/worktrees/sdlc-evals-9f281d` and `sdlc-skills-b90697`, then `git branch -d` both branches). Add `.claude/worktrees/` to `.gitignore`.
2. Delete the stale `# Stub: exits 1 until ... M4` comment in `Makefile`.
3. Make the hooks fail closed. Each hook starts with: if `jq` is missing, print "Blocked: jq is not installed, so this safety check cannot run. Install it with `brew install jq`." and exit 2. Today a missing `jq` gives an empty path and the hook exits 0, which allows the edit.
4. Add the same secret scan as a git `pre-commit` hook (`scripts/pre-commit`, installed by `make hooks`), so commits made outside Claude Code are scanned too. The Claude Code hook only sees commits Claude runs.

Exit criteria
- `git worktree list` shows one entry. `make lint` still passes.
- With `jq` renamed off the PATH in a subshell, asking Claude to edit `data/eval/answer_key.csv` is blocked with the jq message.
- A manual `git commit` of a file with a fake key is refused by the pre-commit hook.
- Commit: `fix(sdlc): hooks fail closed, pre-commit secret scan, worktree cleanup`.

## M7. Give Claude a way to see the app

Files that change: `tests/test_app.py` (new), `.mcp.json` (new, project scope), `.claude/agents/verifier.md`, `CLAUDE.md`, `specs/review-app-acceptance.md` (new).

Layer 1, content checks with no browser (in `make test`):
- `tests/test_app.py` uses `streamlit.testing.v1.AppTest` to run `app/review.py` on `data/demo/sample_list.csv` and asserts: KnowBe4 is flagged, every loan row shows a filing link, `Not A Real Company Xyzzy` shows as not found, the judge checkbox is off by default.

Layer 2, Claude looks at the real page:
- `specs/review-app-acceptance.md` lists what the screen must show, in plain words, one line each, written from the analyst's view. This is the "desired output" the screenshot is compared against.
- Install Playwright MCP at project scope so it is in git for every session and the verifier:
  `claude mcp add --scope project playwright -- npx @playwright/mcp@latest --headless --isolated --allowed-origins "http://localhost:8501"`
- Verifier gets a step 6: start `make run` in the background, open `http://localhost:8501`, load the demo list, take a screenshot of each screen, compare against `specs/review-app-acceptance.md`, report each line as met or not met with the screenshot path. Stop the app after.
- `CLAUDE.md` Verifying block: "For any change under `app/`, also run the verifier's browser step."

Exit criteria
- `make test` shows the new AppTest tests passing.
- `claude mcp list` shows `playwright` connected.
- Run the verifier. It reports every acceptance line with a screenshot. Break one thing on purpose (hide the filing link column) and the verifier reports that line as not met.
- Commit: `feat(sdlc): AppTest checks and browser verification against acceptance spec`.

Risk: `--allowed-origins` is not a security boundary per the Playwright MCP docs. The data rule (nothing leaves the machine) is kept by running the judge off and by the browser only ever being pointed at localhost in the verifier's instructions. Say so in the report.

## M8. First full Stage 2: intent to spec to plan for a real feature

Feature: usage and quality instrumentation, needed by Stage 6 (monitoring) and by the value gate (did analysts use it).

1. Use the `intent-md` skill: `intent/instrumentation.md`. Problem: we can't tell who ran a list, how many names needed review, what the judge cost, or whether match quality is drifting.
2. Stage 2 prompt in a fresh session: "Read intent/instrumentation.md and produce specs/instrumentation.md for this codebase. Apply the skills available to you. Describe clearly any areas of concern, especially where policies contradict." Expect a flagged concern: logging company names would break the data-handling skill.
3. Resolve each flagged concern in the spec. Commit intent and spec together.
4. Plan mode on the spec: `plans/instrumentation.md` with files that change, order, risks, proof. Commit.
5. Do not build yet. Building is day 3.

Scope the spec to: JSON logs with a request id, Langfuse traces on judge calls only (cost, latency, verdict, no company names in the trace input when `ERM_USE_JUDGE` is off), a `run_metrics` table (names in, names matched, names needing review, flags, duration).

Exit criteria
- Three commits: intent, spec (with its flagged concerns resolved), plan.
- `git log --format='%h %ad %s' -- intent/ specs/ plans/` shows the chain with timestamps. That output is the audit trail you show in the interview.

## Order

M6 (30 min) → M7 (1.5 hours) → M8 (1 hour). M7 and M8 can run in parallel worktrees: they touch different files.

## After day 2: GitHub review workflow

- 2026-11-07: `.github/workflows/review.yml` runs `REVIEW.md` on every pull request. It comments with the run's own `GITHUB_TOKEN` (read code, comment on pull requests), not the Claude GitHub App, so no outside app gets standing access to the repo. Chosen by Alexandre in PR #3.
