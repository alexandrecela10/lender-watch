# Spec: catch drops in AI matching quality before users see them

Source: `intent/ai-drift-tracking.md` (commit `739c5d9`). Status: draft, 2026-11-07, pending Alexandre's review.
Evidence: the repo's code, one offline evaluation and one live run. No LP analyst has been interviewed. The pain is inferred.

## Bottom line

- A new check asks the AI judge again, live, about the answer-key pairs that decide a match.
- It runs on every pull request that changes the judge, and every Monday with no change.
- It fails if precision drops below 0.97 or recall below 0.90, and GitHub emails Alexandre.
- One run makes about 145 judge calls, takes about 8 minutes, and should cost under $1. It stops at $3.
- It sends only public filing names to Anthropic, and skips cleanly when the API key is absent.
- Not in this build: alerts on real-use run records (Stage 6). Too few real runs exist yet.

## Concerns and resolutions

| # | Concern | Decision | Why |
|---|---|---|---|
| 1 | The labels are Claude's. The check measures agreement with a Claude labeller, so a blind spot both share stays invisible. | Say so on every result. Keep the 2 November judge answers as a fixed reference, so the check also shows how many verdicts changed. | A count of changed verdicts flags a shift even when the labels can't. |
| 2 | The floors are loose. Precision 0.97 allows about 3 wrong loans in 100 before failing; today there are 0. | Keep the floors as the failure line. Also report false matches as a count, and treat any rise above 0 as a warning shown on the pull request. | Failing on one false match would block on noise we haven't measured yet (concern 4). |
| 3 | The exact-name rule exists twice: in the product (`erm/api.py`) and in the eval (`eval/offline.py`). A change to the product copy isn't tested. | Move the rule into one shared function that both import. | One rule, one test. Otherwise the check tests code the product doesn't run. |
| 4 | Run-to-run variation is unobserved, so "worse than last time" has no tolerance yet. | The first build runs the check 3 times and records the spread. Until then only the floors fail; other changes are reported. | No invented tolerance. |
| 5 | Batch costs half, but can take up to 24 hours, longer than a CI job runs. | Live calls, one at a time. | About 8 minutes fits a CI job. The saving is under $0.50 a run. |
| 6 | A refusal fallback can answer with another model, whose cost is unknown to us. | Record which models answered. A cap on calls (250) backs up the cap on cost ($3). | A null cost must not slip past the cost cap. |
| 7 | GitHub turns off scheduled workflows after 60 days with no repo activity. | The weekly job's summary says when it last ran. Noted in the README. | A silent stop looks like "no drift". |
| 8 | Pull requests from forks don't get the secret. | They skip with a message. Only Alexandre's own pull requests and the schedule spend money. | No stranger can run up the bill. |

## Problems this solves

| Problem | Today | Hypothesis (if/then/because) | Success metric (target) | Expected impact |
|---|---|---|---|---|
| A judge change merges without a live check | 0 of judge changes get a live check (observed: the gate replays the 2 November answers) | If a change to the judge triggers the live check, a drop is caught before merge, because CI fails the pull request | Judge changes merged with a passing live check: 100% | Wrong-loan regressions stop before users see them. Their number today is unobserved |
| A model update behind the same name goes unseen | 1 live run on the answer key, ever (2 November) | If the check runs weekly, a model change shows within 7 days, because the answers change with no code change | Weeks with a completed live run: 100% | Time to detect a model change: 7 days at most. Today unbounded |

**Must not get worse:** precision 1.000 and recall 0.936 on the replayed gate; 0 names from private lists sent anywhere; CI passes with no API key; the judge stays off by default in the product.

**Not tackled:**
- Alerts on real-use run records (Stage 6). Missing: real runs. There are 4 local rows, all tests, and the hosted app's records reset on restart.
- New answer-key pairs from a new quarter. Missing: a decision on who labels them.
- A GitHub issue on failure. Missing: a need beyond GitHub's failure email.

## 1. The live check: `eval/live.py`

**What goes in.** The answer-key pairs from `data/eval/scored_pairs.csv`, with company name, sector, owner, borrower text and two filing rows. Only pairs the chosen method sends to the judge are asked: a wider name hit that the exact-name rule doesn't settle. Today that's about 145 of 1,028.

**What it does.**
- Asks the judge about each pair, live, through `erm.match.judge.judge`, the same call the product makes.
- Scores the result with the same scorer as the replayed gate.
- Compares it with the floors in `evals/thresholds.yaml`, and with the 2 November reference answers.
- Stops at $3 or 250 calls, whichever comes first, and exits with a failure saying which limit was hit.

**What comes out.** One summary, printed and written to the GitHub job page:

```
live judge check, 2026-11-09, model claude-opus-5-5 (145 calls)
precision 1.000 (floor 0.97)   recall 0.936 (floor 0.90)
false matches 0 (reference 0)  verdicts changed since 2 November: 3 of 145
cost $0.67  time 7m 50s        labels are Claude's, not checked by a person
PASS
```

The numbers above are an example, not a result.

**Options.**
- `--dry-run` lists the pairs and the estimated cost, with no network.
- `--repeat 3` runs three times and prints the spread, for concern 4.

**Rules.** No key means exit 0 with "skipped: no ANTHROPIC_API_KEY". Logs follow the instrumentation allowlist, so company names reach no log line. The summary shows counts only.

**Example and its counterfactual.** Say a prompt edit makes the judge accept "Wheel Pros" for "PROS". That pair is in the answer key with label "no match", so false matches go from 0 to 1. The pull request shows a warning, and precision falls to about 0.994. Had the judge accepted wrong borrowers for 6 pairs, precision would fall below 0.97 and the check would fail the pull request.

## 2. One exact-name rule

`is_clear_exact` moves to `erm/match/rules.py`. `erm/api.py` and `eval/offline.py` both import it. The replayed gate must still print precision 1.000 and recall 0.936.

## 3. The workflow: `.github/workflows/live-eval.yml`

- **Runs on:**
  - pull requests that touch `erm/match/`, `eval/live.py`, `eval/compare.py`, `evals/thresholds.yaml` or `data/eval/answer_key.csv`
  - every Monday at 04:00 UTC
  - by hand
- **Secret:** `ANTHROPIC_API_KEY`, added by Alexandre. Never printed.
- **Timeout:** 20 minutes.
- **Failure:** the job fails. GitHub emails the person who last changed the schedule, which is Alexandre.

## Acceptance checks

Each is a test in `tests/test_live_eval.py` unless marked. None calls Anthropic.
1. `--dry-run` lists the pairs to judge and an estimated cost, with no network.
2. A fake judge that repeats the 2 November answers gives the same precision and recall as the replayed gate.
3. A fake judge that accepts 6 wrong pairs fails the check. One that accepts 1 passes, with a warning that false matches rose.
4. A fake judge costing $0.05 a call stops at $3, before 250 calls, and exits with "cost cap reached".
5. No key: exit 0 and "skipped". No call is made.
6. The product and the eval import the same `is_clear_exact`. `make evals` still prints 1.000 and 0.936.
7. No log line or summary line contains a company name from the answer key.
8. (Manual, once) Alexandre adds the secret. Three live runs (`--repeat 3`) on `main` complete under $3 each. The spread is written into this spec.
9. `make test`, `make lint` and `make evals` pass.
