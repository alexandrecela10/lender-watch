---
decision_id: "ERM-001"
date: "2026-11-01"
product_area: "Entity Reconciliation Machine"
feature: "LP credit read-through"
prd_stage: "Team Kickoff"
decided_by: "Alexandre Cela"
status: "active"
supersedes: ""
---

# Decision: Build the matching engine first, with the LP read-through as its first use

## What was decided

Build the entity reconciliation engine in 2 weeks, with the LP credit read-through as its first use, and measure it against an answer key.

## Why

- **Coverage is enough to matter:** 144 of 291 PE-owned companies (49%) have a loan with a usable value in Q2 2026.
- **Matching adds less than first thought (corrected 2026-11-02):** plain name matching is right for 94% of loans; the engine reaches 100% on a Claude-labelled key. The 70% first reported was a bug. Other names and bad filer data are the harder work.
- **The stress data is a commodity:** at least 7 vendors sell BDC loan values, and 9fin already flags loans below 90. Matching a client's own list to those loans, with proof, is the gap.
- **Value is assumed, not observed (corrected 2026-11-02):** about $33k of analyst time, mostly coverage rather than savings, and about $14k to $240k of avoided loss per LP a year.

## What was NOT chosen

| Alternative | Why rejected |
|---|---|
| Sell BDC stress data or flags | 7+ vendors already do it; no edge |
| Generic "reconcile any two lists" tool | Weakest value story; buyers pay for an answer, not for matching |
| Look-through overlap for secondaries first | Needs private fund holdings; no public data to build or demo on |
| Wait for LP interviews before building | The answer key and the precision numbers are needed for the interviews and the case study anyway |

## Consequences

**This decision enables:**
- Measured precision and recall for 3 matching approaches on one answer key, so it serves both learning and the case study.
- An engine that other lists and sources can plug into: side projects, other customers.

**This decision prevents:**
- Comparing lender values with GP equity values in v1, because that needs private GP reports.
- Covering lenders that don't file publicly, such as banks.

**Reversibility:** easy to reverse. It costs 2 weeks of one person's time and commits no customer or money.

## Open questions remaining

- [ ] Do LP analysts keep a list of underlying companies, or only GP PDFs? @Alexandre Cela (interviews)
- [ ] Alpha inputs: how often a flagged company is later marked down by the GP, how large the markdown is, and how often an LP decision is priced in the window. @Alexandre Cela (interviews)
- [ ] Recall: an answer key built without using the matcher. @build

## Review trigger

- **Commercial case to No-go:** 3 LP analysts say PitchBook or 9fin already tells them which of their companies are stressed.
- **Engine design to revisit:** loan-level precision stays below 97% after the 2-week build.

---

*Filed to: `outputs/decisions/lp-credit-readthrough-go-scoped-build.md`. Move to `context-library/decisions/` once ratified.*
*Source: `outputs/opportunity-analyses/lp-credit-readthrough-opportunity.md`*
