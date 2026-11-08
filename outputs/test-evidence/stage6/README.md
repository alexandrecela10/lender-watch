# SIMULATED Stage 6 breach: evidence

SIMULATED. Every run record here is made up. No real run or company is involved.

**Result:** the check found 80 of 300 made-up names (27%) needing a person, against an expected range of 6% to 17%. It wrote a draft intent and exited with code 1.

**Command:** `uv run python -m eval.bands --simulate`

**Files**
- `simulated-report.txt`: what the check printed.
- `simulated-runs.csv`: the 20 made-up run records, which lived in a temporary database.
- `SIMULATED-names-needing-review-high.md`: the draft intent. It stays here, not in `intent/`.

**What this shows**
- A share outside the expected range produces a plain-English report and a draft intent, with no AI model and no outside call.

**What this doesn't show**
- Whether the range is right. It comes from one full run (33 of 291 names, 2 November), not from history.
- Any real drift. No real run records were read.
- A diagnosis, a scheduled trigger or a pull request. None of these ran.

No LP analyst has been interviewed. The pain is inferred from public signals.
