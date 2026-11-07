# Spec: catch drops in AI matching quality before users see them

Source: `intent/ai-drift-tracking.md` (commit `739c5d9`). Status: draft, 2026-11-07, pending Alexandre's review.
Evidence: the repo's code, one batch run of the judge on the answer key (2 November) and one live run on the demo list (7 November). Revised after the AI review on PR #2. No LP analyst has been interviewed. The pain is inferred.

## Bottom line

- A new check asks the AI judge again, live, about the answer-key pairs that decide a match.
- It runs on every pull request that changes the judge, and every Monday with no change.
- It fails if precision drops below 0.97 or recall below 0.90, and GitHub emails Alexandre.
- One run makes about 145 judge calls, takes about 8 minutes, and should cost under $1. It stops at $3.
- Each run's result is added to one GitHub issue, which keeps the history and emails Alexandre.
- It sends only public filing names to Anthropic, and skips cleanly when the API key is absent.
- Not in this build: alerts on real-use run records (Stage 6). Too few real runs exist yet.

## Concerns and resolutions

| # | Concern | Decision | Why |
|---|---|---|---|
| 1 | The labels are Claude's. The check measures agreement with a Claude labeller, so a blind spot both share stays invisible. | Say so on every result. The first live run becomes the reference. Later runs count how many verdicts changed against it. | A count of changed verdicts flags a shift even when the labels can't. |
| 2 | The floors are loose. Precision 0.97 allows about 3 wrong loans in 100 before failing; today there are 0. | Keep the floors as the failure line. Also report false matches as a count, and treat any rise above 0 as a warning shown on the pull request. | Failing on one false match would block on noise we haven't measured yet (concern 4). |
| 3 | The exact-name rule exists three times: in the product (`erm/api.py`), the scorer (`eval/compare.py`) and the gate (`eval/offline.py`). A change to the product copy isn't tested. | Move the rule into one shared function that all three import. | One rule, one test. Otherwise the check tests code the product doesn't run. |
| 4 | Run-to-run variation is unobserved, so "worse than last time" has no tolerance yet. | The first build runs the check 3 times and records the spread. Until then only the floors fail; other changes are reported. | No invented tolerance. |
| 5 | Batch costs half, but can take up to 24 hours, longer than a CI job runs. | Live calls, one at a time. | About 8 minutes fits a CI job. The saving is under $0.50 a run. |
| 6 | A refusal fallback can answer with another model, whose cost is unknown to us. | Record which models answered. A call with no known price counts $0.05 toward the cap, 10 times today's live price. The cap on calls (250) is a second stop. | A null cost must not slip past the cost cap. |
| 7 | GitHub turns off scheduled workflows after 60 days with no repo activity. A turned-off job writes nothing. | The CI job on every pull request reads the history issue and warns when the last live run is more than 8 days old. Noted in the README. | A silent stop looks like "no drift", so something outside the weekly job must notice. |
| 8 | Pull requests from forks don't get the secret. | They skip with a message. Only Alexandre's own pull requests and the schedule spend money. | No stranger can run up the bill. |
| 9 | The 2 November answers came from the Batch API, without the refusal fallback. The live check goes through the product's call, which adds it. | Don't compare live verdicts with the batch answers. Report the batch scores once, labelled "batch, 2 November", next to the first live run. | Otherwise a change of call path would read as drift. |
| 10 | The intent asks for each run to be recorded, but a CI job keeps nothing, and `data/metrics.sqlite` only exists on the machine that ran it. | Each run adds one comment to a GitHub issue, "Live judge check history": date, model, scores, false matches, verdicts changed, cost, PASS or FAIL. The next run reads the last comment to compare. | The history survives log expiry, needs no commit to `main`, and the issue's emails reach Alexandre. |
| 11 | A change to the pairs, the reference, the gate or the SDK version also changes what is judged. | Those files trigger the check too (section 3). | The metric "judge changes merged with a passing live check" must cover them. |

## Problems this solves

| Problem | Today | Hypothesis (if/then/because) | Success metric (target) | Expected impact |
|---|---|---|---|---|
| A judge change merges without a live check | 0 of judge changes get a live check (observed: the gate replays the 2 November answers) | If a change to the judge triggers the live check, a drop is caught before merge, because CI fails the pull request | Judge changes merged with a passing live check: 100% | Wrong-loan regressions stop before users see them. Their number today is unobserved |
| A model update behind the same name goes unseen | 0 live runs on the answer key. 1 batch run (2 November) | If the check runs weekly, a model change shows within 7 days, because the answers change with no code change | Weeks with a completed live run: 100% | Time to detect a model change: 7 days at most. Today unbounded |

**Must not get worse:** precision 1.000 and recall 0.936 on the replayed gate; 0 names from private lists sent anywhere; CI passes with no API key; the judge stays off by default in the product.

**Not tackled:**
- Alerts on real-use run records (Stage 6). Missing: real runs. There are 4 local rows, all tests, and the hosted app's records reset on restart.
- New answer-key pairs from a new quarter. Missing: a decision on who labels them.

## 1. The live check: `eval/live.py`

**What goes in.** The answer-key pairs from `data/eval/scored_pairs.csv`, with company name, sector, owner, borrower text and two filing rows. Sent to Anthropic, never logged. Only pairs the chosen method sends to the judge are asked: a wider name hit that the exact-name rule doesn't settle. Today that's about 145 of 1,028.

**What it does.**
- Asks the judge about each pair, live, through `erm.match.judge.judge`, the same call the product makes.
- Scores the result with the same scorer as the replayed gate.
- Compares it with the floors in `evals/thresholds.yaml`, and with the first live run's verdicts, stored by pair id in `evals/live_reference.csv` once that run is accepted.
- Stops at $3 or 250 calls, whichever comes first, and exits with a failure saying which limit was hit.

**What comes out.** One summary, printed and written to the GitHub job page:

```
live judge check, 2026-11-09, model claude-opus-5-5 (145 calls)
precision 1.000 (floor 0.97)   recall 0.936 (floor 0.90)
false matches 0 (reference 0)  verdicts changed since the reference: 3 of 145
cost $0.67  time 7m 50s        labels are Claude's, not checked by a person
PASS
```

The numbers above are an example, not a result.

**Options.**
- `--dry-run` prints the number of pairs, their pair ids and the estimated cost, with no network. No company names.
- `--repeat 3` runs three times and prints the spread, for concern 4.

**Rules.** No key means exit 0 with "skipped: no ANTHROPIC_API_KEY". Logs follow the instrumentation allowlist, so company names reach no log line. The summary shows counts only.

**Example and its counterfactual.** Say a prompt edit makes the judge accept "Wheel Pros" for "PROS". That pair is in the answer key with label "no match", so false matches go from 0 to 1. The pull request shows a warning, and precision falls to about 0.994. Had the judge accepted wrong borrowers for 6 pairs, precision would fall below 0.97 and the check would fail the pull request.

## 2. One exact-name rule

`is_clear_exact` moves to `erm/match/rules.py`. `erm/api.py`, `eval/compare.py` and `eval/offline.py` all import it. The replayed gate must still print precision 1.000 and recall 0.936.

## 3. The workflow: `.github/workflows/live-eval.yml`

- **Runs on:**
  - pull requests that touch `erm/match/`, `eval/live.py`, `eval/compare.py`, `eval/offline.py`, `evals/`, `data/eval/answer_key.csv`, `data/eval/scored_pairs.csv`, `data/eval/judge_results.csv` or `uv.lock`
  - every Monday at 04:00 UTC
  - by hand
- **Secret:** `ANTHROPIC_API_KEY`, added by Alexandre. Never printed.
- **Timeout:** 20 minutes.
- **Record:** after every run, one comment on the issue "Live judge check history". It needs `issues: write`.
- **Failure:** the job fails, and its comment says FAIL. Alexandre gets the issue's email, and GitHub's failure email goes to whoever last pushed the schedule. Pushes go through Alexandre's account.

## Acceptance checks

Each is a test in `tests/test_live_eval.py` unless marked. None calls Anthropic.
1. `--dry-run` lists the pairs to judge and an estimated cost, with no network.
2. A fake judge that repeats the 2 November answers gives the same precision and recall as the replayed gate.
3. A fake judge that accepts 6 wrong pairs fails the check. One that accepts 1 passes, with a warning that false matches rose.
4. A fake judge costing $0.05 a call stops at $3, before 250 calls, and exits with "cost cap reached". A fake judge whose cost is unknown also stops at $3, counting $0.05 a call.
5. No key: exit 0 and "skipped". No call is made.
6. The product, the scorer and the gate import the same `is_clear_exact`. `make evals` still prints 1.000 and 0.936.
7. No log line, summary line, dry-run line or history comment contains a company name from the answer key.
8. The history comment parses back: the next run reads the date, scores and verdict count from it.
9. (Manual, once) Three live runs (`--repeat 3`) on `main` complete under $3 each. The spread is written into this spec, and the first run becomes the reference.
10. `make test`, `make lint` and `make evals` pass.
