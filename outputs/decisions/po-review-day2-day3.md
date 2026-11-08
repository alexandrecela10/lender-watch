# Product owner review: SDLC day 2 and day 3, main at f16b109

**Written by a fresh AI agent, not a person. This is not Alexandre's approval.** Date: 2026-11-08.

## Decision

**Accept with conditions.** The engine work matches its intent. The controls around it are weaker than the documents say.

**Conditions, in order:**
1. Fix finding 1 before anyone uses the judge in private mode on a private list.
2. Alexandre picks one route for D4 (finding 3).
3. Make the live check block merges (finding 2).
4. Write one plan-departure rule and enforce it (finding 4).
5. Restore the browser check, or stop claiming it (finding 5).

**Context:** No LP analyst has been interviewed, so the pain is inferred. All labels are Claude's. The live check measures agreement with Claude's labels, not truth.

## Findings

| # | Finding | Evidence (file:line) | Severity | What to do |
|---|---|---|---|---|
| 1 | **Confirmed: one user's judge setting reaches another user's session, in private mode.** Names can go to the AI provider with that user's box unticked. Example: A leaves the box off and B ticks it, then A answers a match. A's other unclear candidates go to the judge. Had the client been per session, no call would be made. Public mode is safe: each visitor has a copy, and the judge is forced off. | `app/review.py:52-69` (one cached engine), `:388` (set per click), `:109-113` (answer reuses it), `:75`, `:377` (public). `erm/api.py:204,211,217` (read per pair). Fake-judge test, nothing sent: A's box off, 13 calls for A's name after B's click. Simulated mid-run click: 10 calls. `specs/instrumentation.md:31` says "logged as a follow-up", but no other file on main records it. | High | Keep the client per session and pass it into each call. Add a two-session test. Until then, run one tab only. Bind private mode to localhost: `app.log` shows a network URL. |
| 1a | The run record can be wrong after this bug. A run logged the judge as off and made 10 judge calls. | Fake-judge test: `('app', 0, 10)` in `run_metrics`. `app/review.py:94`. `specs/instrumentation.md:31` says it records the setting each call used. | Medium | Set `judge_on` from the calls made, or fix with finding 1. |
| 2 | The live check doesn't block a merge. The intent's target is "before merge". PR 8 merged at 16:30:22. Its live check ran from 16:34:01 to 16:40:06. PR 7 also merged before its run ended. | Branch protection requires `checks` only (GitHub API). `gh pr view 7` and `8`, run 42500012901. `intent/ai-drift-tracking.md:22`. `specs/ai-drift-tracking.md:40`. Playbook p.35. | High | Make it a required check. A path filter leaves it pending on other pull requests, so add a gate job that always reports. |
| 3 | **D4 was not met as the plan and spec say.** It ran on a local machine, on unmerged code, not on `main`. The history issue has none of the three runs. The numbers look real. The log still says `none`. | See the D4 table below. | High | Alexandre's choice: run it by hand on `main` with repeat 3 (about $2), or amend plan and spec to say it ran locally. Either way, fix the drift row. |
| 4 | **The stated rule and the enforcement differ.** The playbook says update the plan in the same commit, and consider a hook. `CLAUDE.md` says write a separate log. Nothing enforces either. The tool always exits 0, checks file names only, and appears in no hook or CI job. | Playbook p.20 step 7. `CLAUDE.md:25`. `eval/plan_drift.py:61-83`. `.claude/settings.json`. `.github/workflows/ci.yml`. `scripts/pre-commit` scans keys only. `REVIEW.md:14` makes only spec departures Important. | High | Pick one rule. Suggested: a CI step fails when a pull request changes a file its plan step doesn't name and the plan is unchanged. |
| 4a | The log itself was followed half the time. I1 to I4 were logged in the step commits. D1 to D3 came in one later commit. D4 and I5 can't run through the tool, because neither step has a `Files:` line. So the D4 row was written by hand. Three D3 fix commits came after its row and aren't logged. | `plans/ai-drift-tracking-drift.md:7-9,15`. Commits `f7e9179`, `f930f11`, `2555d2c`, `3fffb5a`. `planned_files` raises "step D4 has no 'Files:' line" (`eval/plan_drift.py:37-38`). | Medium | Give every step a `Files:` line. Make a missing line a failure. |
| 4b | Departures sit in the log, not in the plan. The file lists for I2, I3, I4 and D3 still omit the files that the log flags. Example: D3 changed `eval/live.py`, and its list doesn't name it. The verifier uses a third source: the plan's table, and only if handed a plan. | `plans/instrumentation.md:50,61,72`. `plans/ai-drift-tracking.md` D3 `Files:` line. `.claude/agents/verifier.md:26`. | Medium | Update the plan's file lists. Use one source for the tool and the verifier. |
| 5 | **The browser check ran on one afternoon only.** Four runs, 17:04 to 17:41 on 7 November, all before its commit at 17:42, all in one worktree. None since. `app/review.py` changed afterwards at `90a570a`, and `CLAUDE.md` requires the check for that. | Session logs: 4 files hold every Playwright call. Verifier at I5: no browser tool. Retest on 8 November: "NOT RUN", tools unavailable. `CLAUDE.md:33`. `plans/instrumentation.md:87` leaves the browser out of I5. | High | Find why the tools don't reach the verifier (cause unknown; `.claude/settings.local.json` enables the server). Then run it once on `main`. |
| 5a | The check has never been fully green. In all four runs, steps 4 and 5 failed because the worktree lacked the data file. Run 3 met all lines. Run 4 failed A8 and one test, which fits the planned deliberate break. Screenshots live in `/tmp`, so no record is kept. The committed I5 screenshots were not taken by the verifier. | Verifier reports in session logs `162b32f9`, `e41eaf1d`, `b39a2c6b`, `3284c9b8`. `/tmp/erm-verify/screen*.png`, dated 7 November. | Medium | Commit the verifier's report and screenshots per app change. Say in `verifier.md` that missing tools means failed, not skipped. |
| 6 | Reviews don't gate merges. Six pull requests merged in under 8 minutes on 8 November. On five of them, an AI review arrived after the merge. PR 5 merged with its D4 finding (Important) open since 7 November. No approving review is recorded. | PR 5 merge 16:24:27, reviews 16:25:01 and 16:25:24. PR 4 merge 16:25:48, review 16:26:08. PR 6 merge 16:27:32, review 16:28:00. PR 7 merge 16:28:59, review 16:29:45. PR 8 merge 16:30:22, review 16:30:39. Required approvals: 0. `REVIEW.md:3`. | Medium | Require the `review` check, and wait for it. Record approval as a review, so the audit trail shows who accepted. |
| 7 | The spec and plan disagree with the build, and with each other. | Timeout: `specs/ai-drift-tracking.md:92` says 20, `.github/workflows/live-eval.yml:50` says 45. `plans/ai-drift-tracking.md:14` against `:103` on which step first sends data. `:90` still says noise is unmeasured. | Medium | Correct these lines. `REVIEW.md:14` treats an unstated spec departure as Important. |
| 8 | The early stop can call a short burst an outage. Three failures in the first 20 calls end the run as ERROR. That is 2% of 145 calls. The spec says over 10%. | `eval/live.py:104`. `specs/ai-drift-tracking.md:33`. Raised as a nit on PR 6. | Low | Measure against the 145 pairs. |
| 9 | The "warning only" freshness step can fail the required check. It runs under `bash -e`, so a GitHub API error turns CI red. | `.github/workflows/ci.yml:31-48`. | Low | Add `continue-on-error: true`. |
| 10 | The weekly run and the failure path have never run on GitHub. All 8 completed runs passed. The first Monday run is 9 November, 04:00 UTC. So the 7-day detection target is unobserved. | `gh run list`. `.github/workflows/live-eval.yml` cron line. | Low | Check issue 9 on 10 November. Force one failing run with a test floor. |

## D4 exit criteria, checked against the source

| Criterion (`plans/ai-drift-tracking.md:76-81`) | Met? | Evidence |
|---|---|---|
| Run by hand on `main` with repeat 3 | No | `plans/ai-drift-tracking-drift.md:17` says local, with the `.env` key. |
| Three runs complete, each under $3 | Yes, locally | Build session log: $0.65 to $0.66 each, 1.000 and 0.936, verdict changes `[1, 0]`. |
| History issue shows all three | No | Issue 9 has one comment, from one run on 8 November. |
| Spread written into the spec | Yes | `specs/ai-drift-tracking.md:24`. It doesn't say where it was measured. `:109` still says `main`. |
| Reference holds the first run's verdicts | Yes | `evals/live_reference.csv`, 145 rows, identical to the local run's copy. |
| Pull request merged | Yes | PR 8, before its live check ran (finding 2). |

The drift row reads `none | none` (`:15`), which is wrong: the departure is only in a note below it. The local runs also fall outside the written data exception, which names the CI check only (`.claude/skills/data-handling/SKILL.md:12`). The data was public. I found no record of approval for that route.

## What passes

- **CI on main:** 73 tests pass, lint is clean, and the offline gate gives 1.000 and 0.936 (run after PR 8).
- **Live check:** 8 GitHub runs completed, 1 on `main`. All gave 1.000 and 0.936 with 0 false matches, where I read the results. Each cost about $0.66.
- **One exact-name rule:** D1 moved it to `erm/match/rules.py`, and all callers import it.
- **Logging limits:** names are blocked by an allowlist, and a committed proof shows 0 names in 24 stored traces.

## Not checked

- I did not call the AI provider or run the live check. The experiment used a fake judge in a temp folder.
- I did not re-read every instrumentation acceptance check against code. For those I relied on CI and the I5 proof file.
- I did not repeat the trace read-back.
