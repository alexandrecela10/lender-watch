# Plan: catch drops in AI matching quality before users see them

Date: 2026-11-07. Owner: Alexandre. Build: Claude Code, one pull request per step.
Source: `specs/ai-drift-tracking.md` (PR #2), from `intent/ai-drift-tracking.md`.
Evidence: the repo's code, one batch run and one live run. No LP analyst has been interviewed. The pain is inferred.

## Summary

- Four steps, each one pull request. CI and the AI review must pass before merge.
1. One exact-name rule, shared by the product, the scorer and the gate.
2. The live check itself, tested with a fake judge, so nothing is sent.
3. The GitHub workflow, the history issue and the stale-schedule warning.
4. Three live runs on `main`, to measure the spread and set the reference.
- Step 4 is the only one that spends money or sends names, all public. It stops at $3 a run.
- Matching, flags and the values shown don't change.

## Files that change

| File | New or changed | What changes |
|---|---|---|
| `erm/match/rules.py` | New | `is_clear_exact(f)`, moved from `erm/api.py` |
| `erm/api.py` | Changed | D1: imports `is_clear_exact` from `erm/match/rules.py`. D2: `call_judge` takes an optional `details` dict that receives the answering model and cost |
| `eval/compare.py`, `eval/offline.py` | Changed | Use `is_clear_exact` instead of their own copies |
| `eval/run_full_list.py` | Changed | Imports from the new place |
| `eval/live.py` | New | Pair selection, live judging with caps, scoring, reference compare, summary, history comment |
| `evals/thresholds.yaml` | Changed | Adds `live: {cost_cap_usd: 3, call_cap: 250, unknown_call_usd: 0.05, stale_days: 8}` |
| `tests/test_live_eval.py` | New | Spec acceptance checks 1 to 8 |
| `.github/workflows/live-eval.yml` | New | Trigger paths, Monday schedule, by hand. On `main` (schedule or by hand) it adds a history comment; on a pull request it comments on that pull request only |
| `.github/workflows/ci.yml` | Changed | Warns when the last live run is more than 8 days old |
| `README.md` | Changed | One line on the 60-day schedule rule |
| `.claude/skills/data-handling/SKILL.md` | Changed | Check 3 names the one approved exception: the CI live check, on answer-key data only |
| `evals/live_reference.csv`, `specs/ai-drift-tracking.md` | Changed in step 4 | Reference verdicts by pair id, and the measured spread |

## Order

### D1. One exact-name rule

Files: `erm/match/rules.py`, `erm/api.py`, `eval/compare.py`, `eval/offline.py`, `eval/run_full_list.py`, `tests/test_live_eval.py`.

Exit criteria
- `uv run pytest tests/test_live_eval.py -k shared_rule` passes: the three callers use one function (spec check 6).
- `make evals` prints precision 1.000 and recall 0.936.
- `make test` and `make lint` green. Pull request merged.

### D2. The live check, offline

Files: `eval/live.py`, `erm/api.py`, `evals/thresholds.yaml`, `tests/test_live_eval.py`.
The live judge is `erm.api.call_judge`, the product's call (spec concern 12). The judge is passed in, so tests use a fake one. No test calls Anthropic.

Exit criteria
- `uv run pytest tests/test_live_eval.py` passes: spec checks 1 to 5 and 7 to 10.
- `uv run python -m eval.live --dry-run` prints 145 pairs, pair ids only, and an estimated cost.
- `make test`, `make lint` and `make evals` green. Pull request merged.

### D3. The workflow

Files: `.github/workflows/live-eval.yml`, `.github/workflows/ci.yml`, `README.md`, `.claude/skills/data-handling/SKILL.md`.

Rules from the third spec review (0 Important, 5 nits):
- Only runs on `main` add to the history issue, by schedule or by hand. A pull-request run comments on its own pull request, so an unmerged judge never becomes "the last run".
- The staleness warning and the last-run comparison read only completed `main` runs (PASS or FAIL), posted by `github-actions`. ERROR, INCOMPLETE and skipped runs don't reset the clock, and nobody else's comment counts.
- ERROR and INCOMPLETE exit 1, so a judge change can't merge green during an outage.
- The caps apply to each repeat: `--repeat 3` may spend up to $9, about $2 expected.
- The job timeout is 45 minutes, not the spec's 20, because a run by hand with repeat 3 takes about 25 minutes.
- `eval.live` calls Anthropic only with `--live`, so running the module by mistake sends nothing (AI review on #6).
- Trigger paths add `erm/textparse.py`, `data/public/holdings.parquet` and `.github/workflows/live-eval.yml`.

Exit criteria
- The pull request runs the live check, because it touches `evals/`. It completes under $3 and comments on the pull request, not the history issue. This is the first live run on GitHub.
- Every YAML file parses (`uv run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"`).
- CI on the pull request shows the stale-schedule step.
- Pull request merged.

### D4. Measure the spread and set the reference

Run the workflow by hand on `main` with `--repeat 3`.

Exit criteria
- Three runs complete, each under $3. The history issue shows all three.
- The spread of precision, recall and changed verdicts is written into the spec, replacing "unobserved".
- `evals/live_reference.csv` holds the first run's verdicts by pair id. Pull request merged.

## Options not chosen

| Option | Why not |
|---|---|
| Batch calls | Can take 24 hours, longer than a CI job; saves under $0.50 a run |
| Compare with the 2 November batch answers | Different call path, so a change would read as drift (spec concern 9) |
| Store history by committing to `main` from CI | Branch protection blocks it, and a bot commit per week clutters the audit trail |
| Fail on any false match above 0 | Run-to-run noise is unmeasured; it waits for D4 |
| Run in parallel threads | Rate limits are unknown on this key; one at a time fits in about 8 minutes |

## Risks

| Risk | What it would break | Mitigation |
|---|---|---|
| A rate limit or outage mid-run | A failed run reads as drift | A failed call is counted as an error and left out of the scores (spec concern 13). Over 10% errors marks the run ERROR, not FAIL, and stops it early |
| The cap stops a run early | Scores computed on part of the key | A capped run is marked INCOMPLETE and never compared |
| D1 changes what the rule returns | Matching changes in the product | `make evals` must still print 1.000 and 0.936, and the shared function keeps the product's exact logic |
| A company name in a log or comment | A leak against the logging rules | Spec check 7 scans every output line for every answer-key name |
| The history issue is closed or renamed | The next run has nothing to compare with | The workflow finds the issue by title, and creates it if missing |

**Riskiest step: D3.** It's the first that sends anything and spends money, and it runs on GitHub, where a mistake is harder to see than on this machine.
