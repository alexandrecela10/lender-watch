# SIMULATED: Intent: more names than expected need a person's review

SIMULATED. These are made-up run records in a temporary database. No real run or company is involved.

Author: `eval/bands.py`, a script. No AI model wrote this. Status: draft, for a person to correct or dismiss before anything is built.
Source: run records from 2000-01-01 to 2000-01-20, compared with the provisional range in `evals/bands.yaml`.
Evidence: made-up run records. No LP analyst has been interviewed. The pain is inferred from public signals.

## Problem

- Who has it: LP analysts who confirm unclear company matches before they rely on a lender's loan value.
- What went wrong: 27% of names needed a person's review, and the expected range for this many names is 6% to 17%.
- Why it matters: Each extra name is a match an analyst confirms by hand, so a list takes longer to get through.
- The case: 80 of 300 names across the latest 20 runs with the AI judge on (made up), from our run records.
- The cause is unobserved. The records hold counts only, so a person must look at what changed.

## Proposed outcome

A person learns why the share moved, then decides to fix, schedule or dismiss.

What should change:
- Share of names needing a person's review: today 27%, target back inside 6% to 17%, or a corrected range if this level is the new normal.
- Time from this finding to a decision: unobserved.

What must not get worse:
- Wrong loans shown to an analyst. Precision on the answer key stays at or above the 0.97 floor.
- Values shown without a filing link: 0.

## Affected users and systems

Users: LP analysts on a private equity funds team.
Systems: matching in `erm/`, saved decisions, the optional AI judge, the run records.

## Constraints

- Public data only. Never name an organisation Alexandre is applying to.
- Every fact keeps its source.
- Run records hold counts only. Diagnosis must not add company names to them.
- The AI judge stays off by default.
- The expected range is provisional: one run on 2026-11-02, 33 of 291 names.

## Open questions

- Did the judge's model or instructions change between these runs? If yes, re-run the live check first.
- Were different kinds of lists run? If yes, the range may be wrong rather than the product.
- Did saved answers from people lower the share? If yes, a list run twice is not a fair comparison.
- Is the range right? Decide after a quarter of real runs. If this finding is dismissed, record why and adjust the range.
