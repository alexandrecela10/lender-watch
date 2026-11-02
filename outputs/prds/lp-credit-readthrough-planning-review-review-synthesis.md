---
prd: lp-credit-readthrough-planning-review.md
review_date: 2026-11-02
stage: Planning Review
agents: engineer, designer, executive, legal, uxr, skeptic, customer (all Claude, simulated)
---

# Review synthesis: Lender Watch PRD and v1

**Assessment:** the engine is much sounder after this review, but the commercial case is weaker. Recommendation: stop new features after this fix round until LP evidence arrives.

**Evidence:** all seven reviewers are Claude. No real analyst, lawyer or engineer was asked. I checked the blocker findings against the code and data before changing anything.

## What the review changed

| Before | Now | Why |
|---|---|---|
| 31 of 144 companies flagged (22%) | **14 of 144 (10%) flagged, 16 worth a look** | The old rule used the lowest single position. 11 flagged companies average 90% or more, such as Bullhorn on one $68k position |
| $540k alpha per LP a year | **About $14k to $240k, all assumed** | Lower flag rate, plus a low case. The old figure implied 0.72 full $750k decisions a year |
| Results "around day 42" | **About day 62 as built** | We read SEC's monthly data sets. Day 42 is the filing date. SEC's publish date isn't verified |
| "Runs on their machine, so the list stays private" | **True only with the AI judge off, now the default** | The judge sends name, sector and owner to Anthropic |
| 11% of names need a person | **11% with the judge on, 45% with it off** | Off is the private default: 132 of 291 names and 422 questions |
| Companies found: "about 92%" | **86%, below the 90% target** | Name research isn't wired into the product |

## Critical blockers

| # | Blocker | Flagged by | Status |
|---|---|---|---|
| 1 | Rejected loans came back: Brightview Landscapes for BrightView, 3 rows on the full list | Engineering | Fixed, re-measured |
| 2 | Canadian loans read about 72% of par, because principal is local and value is US dollars | Engineering | Fixed for Canadian-style rows. Euro loans still read about 108% |
| 3 | Flags counted single small positions | Skeptic | Fixed: size-weighted flag |
| 4 | Names sent to Anthropic against a privacy promise | Legal, engineering, customer | Fixed: off by default. Whether fund terms allow it on needs a lawyer |
| 5 | Unclear companies read "No public lender data found" | Design, engineering | Fixed |
| 6 | Review cards showed internal keys and no evidence; queue mixed in other lists | Design | Fixed: borrower name, filing text and link, current list only |
| 7 | Download lost the analyst's columns and filing links | Design, engineering | Fixed: same columns plus an All loans sheet |
| 8 | One failed AI call stopped the whole run | Engineering | Fixed in code; not tested against a live failure |
| 9 | Analysts couldn't reject a wrong match or change an answer | Engineering, design | Fixed |
| 10 | `uv run pytest` failed, and fixing it would have run a paid script | Engineering | Fixed |
| 11 | No person has checked the labels | Executive, skeptic, customer | **Open: needs Alexandre** |
| 12 | No evidence that any LP wants this or would act on a flag | UXR, executive, skeptic | **Open: needs interviews** |

## Important gaps, not fixed

- **Prediction:** we have two quarters, so no test of whether a flag precedes anything. 9 of 14 flagged were already below 90 last quarter. Older SEC data sets could test later falls.
- **Refresh:** a new quarter needs a manual download and two dates changed in code.
- **Missing filers (closed after this review):** all April to September data sets are now loaded, adding 5 filers including Hercules. No company's flag changed. 4 filers still have Q1 rows but no Q2 rows.
- **Reuse:** no connector interface exists, so "any source plugs in" is untested. Lists do plug in.
- **Legal:** no terms or liability limit. Charging for flags may raise adviser questions, and statements about named companies need care. A lawyer should review before any customer use.
- **Saved verdicts ignore sector,** so one company's answer applies whatever sector the next list gives.
- **Euro loans** lift an average slightly.

## Conflicting perspectives

| Topic | One view | Other view | Recommendation |
|---|---|---|---|
| AI judge default | Legal: off, because list confidentiality is at stake | Design and customer: off means 45% of names to review, which breaks the 15% limit | Off, since a disclosure can't be undone and extra review can. Revisit with a lawyer's answer |
| Keep building? | Executive: stop until LPs give evidence | Engineering: day 42 timing, refresh and connectors remain | Stop. Reading filings directly matters only if LPs care about the lead |
| How many interviews | PRD and guide: 3 | Executive: 5 by 31 December. UXR: 6 to 8, kill at 3 of 6 | 6, including a secondaries buyer. 3 can't fire the kill test if one person dissents |

## By reviewer

- **Engineering:** 6 blockers, all checked above. Also found the day 62 timing and missing filers. Not checked by that reviewer: live judge, MCP, browser.
- **Design:** 4 blockers, all fixed. Headline leads with the answer; flag rule now shown; flagged companies sort first.
- **Executive:** continue, gated. Differentiation is the client's own list, filing-row proof and local running, all copyable. No price, budget owner or market size exists.
- **Legal:** high risk on list confidentiality, statements about named companies, and securities questions. Not legal advice. Wording now says marked down, not stressed.
- **UXR:** the data supply is evidenced; demand isn't. A vendor demo could end the commercial case without recruiting anyone. The guide also has smaller inconsistencies, such as 15 versus 18 markdowns, not yet fixed.
- **Skeptic:** multiplication was right, logic wasn't. A re-up or co-invest sheds no exposure, and LPs sell fund stakes rather than companies. First question: which real decision in the last two years would a flag have changed?
- **Customer (simulated):** might use it. Wants ranked flags, which now exist. Rejects $540k and any unchecked 100%. Would stop after one wrong loan raised with a GP.

## Decisions for Alexandre

1. **Stop new features until LP evidence?** Recommended: yes.
2. **Add a dated kill?** Recommended: if nobody names an action on a flag and a budget by 31 December, stop the commercial case and keep the engine for side projects.
3. **Raise interviews from 3 to 6, including a secondaries buyer?** Recommended: yes.

## Next

1. Alexandre checks the 50 pairs in `outputs/analyses/answer-key-spot-check.csv`.
2. Book PitchBook and 9fin demos: can a client load its own list?
3. Hold the LP interviews. Ask which past decision a flag would have changed.
