# Intent: catch drops in AI matching quality before users see them

Author: Alexandre Cela, writing as the person who runs and maintains the engine. Status: draft, awaiting correction by the author.
Source: no opportunity analysis. This follows the instrumentation work (`intent/instrumentation.md`) and the playbook's Stage 4 (continuous evals) and Stage 6 (closing the loop).
Evidence: the repo's code, one batch run of the judge and one live run on the demo list. No LP analyst has been interviewed. The pain is inferred.

## Problem

- Our matching quality check replays the answers the AI judge gave on 2 November. It never asks the judge again.
- So a worse judge goes unnoticed: an edit to its instructions, a switch of model, or a model update behind the same name.
- We'd find out only when a wrong loan reaches an analyst, who then raises a false alarm with a fund manager.
- One case: without the judge, plain name search put a wrong loan on 3 of 84 companies, such as "PROS" pulling in Wheel Pros. With the judge, none (`outputs/analyses/matching-comparison.md`). A judge that slips loses exactly that gain.

## Proposed outcome

- Every change to the judge, and once a week with no change, the judge answers the answer key again, live.
- The scores are compared with the agreed floors (precision 0.97, recall 0.90) and with the last live run.
- A drop below a floor fails the check, and GitHub tells me. Each run is recorded with its date, model, scores and cost.
- Later, run records from real use get an alert band, so a drift in real lists is caught too. First metric: share of names needing a person. The band starts provisional, at 11% with the judge on.

What should change:
- Time from a drop in judge quality to someone knowing: today unbounded, because it's only noticed when a wrong loan is spotted. Target: before merge for our own changes, within 7 days for a model change.
- Live judge runs on the answer key: 0 so far. The 2 November answers came from one batch run. Target: one per judge change, plus one a week.
- Cost of one live run: unobserved. Estimate: under $1, about 145 judge calls at roughly $0.005 each, from the 7 November live run on the demo list (24 calls, $0.109).

What must not get worse:
- Precision 1.000 and recall 0.936 on the answer key, as measured on 2 November.
- Names from a private list sent to anyone: 0. The answer key uses public filing names only.
- CI on a pull request still passes when the API key is absent. The live check is skipped, not failed.
- The AI judge stays off by default in the product.

## Affected users and systems

Users: Alexandre now, as the operator. Later, whoever reviews a judge change, and the LP analyst indirectly, who should never see a drift.
Systems: the answer key and judge answers in `data/eval/`, the judge in `erm/match/judge.py`, the eval scripts in `eval/`, the GitHub workflows, the run records in `data/metrics.sqlite`, and the Anthropic API through a GitHub secret.

## Constraints

- Public data only. The live check sends public filing names, with sector and owner, to Anthropic.
- All labels are Claude's. The check measures agreement with Claude's labels, not truth checked by a person. Every document must say so.
- The API key lives in a GitHub secret that Alexandre adds. Never printed, logged or committed.
- A cost limit per run, decided in the spec. A run that would go over it stops.
- Every number shown keeps its source: the run, its date and the model that answered.

## Open questions

- How much do the judge's scores vary between two runs with no change? Unobserved. It decides how far below the last run counts as a drop.
- Live calls or batch? Batch costs half, but can take up to 24 hours, longer than a CI job runs.
- Weekly or nightly? Weekly is cheaper. Nightly catches a model change sooner.
- The answer key covers holdings dated 30 June 2026 only. Should a new quarter's filings add pairs to it, and who labels them?
- Who is told about a failure: GitHub's email to Alexandre, or an issue opened in the repo?
