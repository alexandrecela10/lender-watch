# Plan: SDLC Stage 6, close the loop once

Date: 2026-11-08. Owner: Alexandre. Reviewer: product owner session (chat).
Source: Anthropic AI Native SDLC playbook, Stage 6 (pages 48 to 51). Follows `plans/instrumentation.md`.
Evidence: no real usage history exists yet. No LP analyst has been interviewed. The pain is inferred from public signals.

## Summary

- A script checks one number from our run records: the share of names that need a person's review.
- It compares that share with a provisional expected range, and reports in plain English.
- When the share leaves the range, it writes a draft intent for a person to review.
- We show this once, with made-up run records in a temporary database, marked SIMULATED.
- No AI model runs. No outside call is made. Real limits need run history we don't have.

## Baseline

- **Use 33 of 291 names (11.3%), judge on.** It counts `status == needs_review`, the same rule `run_metrics` stores.
- **Why not 3 of 84 (3.6%).** That counts judge-unsure pairs among name hits in the answer key sample, a different rule.
- On the same 84 companies, the product status gives 11 of 84 (13.1%). So the gap is the rule, not the sample.

## Steps

### S1. Check, simulated breach and tests

Files: `evals/bands.yaml`, `eval/bands.py`, `tests/test_bands.py`.

1. `evals/bands.yaml`: provisional label, baseline and its source, how many recent runs to pool, fewest names to judge on.
2. `eval/bands.py`: read judge-on, finished runs from `run_metrics`. Pool the most recent ones. Compare with the range.
3. Range: baseline plus or minus 3 standard deviations of a yes/no share for that many names. This stands in for rolling history.
4. On a breach, write a draft intent in the `intent-md` format. Problem has 3 to 5 bullets and no code.
5. `--simulate` builds made-up rows in a temporary database and refuses to write to `intent/`.
6. `--open-pr` exists, defaults to off, and refuses simulated drafts. Not used in this build.

Tests: inside the range, breach, no runs yet, no company name in the output, SIMULATED on everything, the pull request option off by default.

Exit criteria
- `make test` and `make lint` pass.
- Commit: `feat(sdlc): provisional range check on names needing review`.

### S2. Make target and docs

Files: `Makefile`, `README.md`, `CLAUDE.md`.

1. One new `bands` target. Nothing else in `Makefile` changes, because another branch is editing it.
2. A short README section.
3. Update the healthy test count and add the command in `CLAUDE.md`.

Exit criteria
- `make bands` reports no runs yet in a clean worktree and exits 0.
- Commit: `docs(sdlc): make bands target and README section`.

### S3. Simulated breach evidence

Files: `outputs/test-evidence/stage6/README.md`, `outputs/test-evidence/stage6/simulated-report.txt`, `outputs/test-evidence/stage6/simulated-runs.csv`, `outputs/test-evidence/stage6/SIMULATED-names-needing-review-high.md`.

1. Run `uv run python -m eval.bands --simulate` once.
2. Save the report, the made-up rows and the draft intent here. The draft stays out of `intent/`.

Exit criteria
- Every saved file says SIMULATED.
- `intent/` is unchanged.
- Commit: `test(sdlc): simulated Stage 6 breach evidence`.

## Risks

- **The range comes from one run.** A real list may differ. The output says so every time.
- **Saved answers lower the share.** A list run twice needs fewer reviews the second time. Only real history shows how much.
- **Small runs swing widely.** Below the fewest-names limit the script says it can't judge yet.

## Not in this build

- No scheduled trigger, no AI diagnosis and no action taken on a breach. The playbook's later tiers need history first.
- The pull request option is written but never run here.
