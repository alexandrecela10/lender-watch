# LP credit read-through: Opportunity Analysis

**Date:** 2026-11-01 · **Owner:** Alexandre Cela · **Status:** Go, scoped
**Evidence:** public filings and commentary only. No LP interviewed yet, so the pain is inferred.
**Corrected 2026-11-02:** the first version had two bugs and one wrong claim. Plain matching was reported as 70% right because of a name-cleaning bug; it is 94%. Half the holding rows were old comparison data. Labels called "by hand" were Claude's. A later review found the flag rule counted single small positions, Canadian loans read as markdowns, and rejected loans could return. Numbers below are re-measured.

## Vision

Every list of company names in private capital links to one company record, with the source row as proof. Today each team matches names by hand, inside each workflow, and starts again every quarter. In this vision a name is matched once, a person confirms it once, and every later workflow reuses the answer.

- **First:** LP analysts see which companies in their funds their lenders have marked down.
- **Next, same engine:**
  - Secondaries buyers find which companies overlap across the funds they price.
  - Lenders track one borrower across lenders and loans.
  - Data teams check a vendor's file against their own.
- **Delivery:** a spreadsheet, a review app, or a tool AI agents call.

Analysts' time moves from matching names to judging what the data means.

## Problem Statement

LP analysts can't see which companies in their PE funds their lenders already value below par. The loan values are public, but no one matches them to the LP's list of companies.

## Current Situation

BDCs, the listed lenders, file every loan and its value about 42 days after quarter end. SEC adds them to its monthly data sets, so about day 62, which is what we read today. GP reports are due 60 to 120 days after. Using the earlier data means finding each company by hand across about 160 filers.

**A concrete case.** Vista owns KnowBe4. Ten BDC funds hold its loans, described 9 different ways. Golub Capital Private Credit Fund valued its loan at 78.5% of par on 30 June 2026, down from 89.7%. All 9 funds with a usable value sit between 77.5% and 78.5%, so lenders agree. It filed on 11 August. An LP matching names sees this on 11 August. An LP waiting for Vista's report gets it by 29 August at best, and that report shows Vista's equity value, not the lenders' view.

## Proposed Solution

An entity reconciliation engine for private capital. It takes the LP's list of company names as written and:

1. **Finds** every BDC loan to each company, across all filers and quarters.
2. **Matches with proof.** An exact-name rule settles clear names. A language model (an AI that reads text) compares name, sector and loan terms on the rest and writes its reason. A person confirms the rest once, and the answer is saved.
3. **Compares** each lender's value against last quarter and against other lenders, loan by loan, each value linked to its filing row.

## Problems, hypotheses and success

| # | Problem | Today | Hypothesis | Success metric (target) | Expected impact | Value opportunity per LP per year (cases × today × gain × value per unit) |
|---|---|---|---|---|---|---|
| 1 | Finding a company's loans | Manual search. A matched company sits in a median of 4 BDC funds under 5 descriptions (observed) | If the engine searches every filer for each name, then the full list is covered each quarter, because search stops being manual | Companies found, of those known to have loans: ≥ 90% | Full list covered. 49% of 291 sampled companies have a loan with a usable value (observed). Companies found: 86%, below target. About 92% if name research were added; it isn't in the product | **Productivity: about $22k.** 980 company-quarters × 10 min to find by hand × 90% saved × $150/hour. Mostly coverage gained, not cost saved: analysts don't search every name today |
| 2 | Wrong matches | Plain name matching: 94% of loans found are right, with errors clustered in 3 of 84 companies (observed) | If a language model judges unclear names on context and the rest go to a person once, then name clashes drop out, because "Apex Group" no longer pulls in Apex Dental | Loan-level precision: ≥ 97% | Wrong loans fall from 6 in 100 to 0 in the test, not yet checked by a person (observed) | **Productivity: about $11k.** 980 company-quarters × 5 min checking matches × 90% saved × $150/hour. Same caveat, and matches are confirmed once, not each quarter |
| 3 | Seeing lender markdowns early | Hand checks on a few names (assumed) | If the engine compares loans across lenders and quarters, weighted by size, then markdowns show about day 62 as built (day 42 if it read filings directly, not built), because BDCs report before most GP reports | Flags a person confirms against the filing: ≥ 90% | 14 of 144 companies flagged in Q2 2026 (observed). 8 fell 3 points or more; 9 were already below 90 last quarter. Whether a flag predicts a GP markdown is unobserved | **Alpha (loss avoided): about $14k to $240k, all assumed.** High: 8 companies later marked down × caught early 10% → 90% × $37.5k ($5M × 15% markdown × 5% chance a decision is priced in the window). Low: 2.4 companies × same gain × $7.5k (1% chance) |

**Must not get worse:** values shown without a filing link: 0.

**Value assumptions (all assumed, none observed yet):**
- **The LP:** 500 underlying companies and $2.5bn of PE exposure, so $5M per company.
- **Cases:** 49% of companies have BDC loans (observed), which gives 245 companies and 980 company-quarters a year.
- **Flags:** 10% of those are flagged (14 of 144, one quarter's snapshot), about 24 companies. 1 in 3 is later marked down by the GP, or 1 in 10 in the low case.
- **Analyst cost:** $150 an hour.

**What the numbers say:** productivity alone is about $33k per LP a year. Today most LPs skip this work rather than pay for it by hand, so those hours are mostly coverage gained, not cost saved. Alpha is about $14k to $240k, and it's the least proven: it needs real markdown rates and decision timing from LP interviews. An earlier $540k counted single small positions as flags and is withdrawn.

**Not tackled:** lender vs GP equity value (needs private GP reports); lenders that don't file, such as banks (only 8 of 59 Shore Capital companies show up); default prediction.

## Value Equation (Hormozi)

| Factor | This solution |
|---|---|
| **Dream outcome** | "I walk into the GP meeting knowing which of our companies their lenders have already marked down, with the filing to show." |
| **Perceived likelihood** | Low before first use. Analysts distrust automatic matching, and one wrong loan means a false alarm with a GP. A filing link on every value and a published precision figure are what earn belief. |
| **Time delay** | Results the day the list is loaded. The benefit lands at the next quarterly review, up to 90 days later. |
| **Effort & sacrifice** | Export the company list, if they keep one (untested). Confirm unclear matches once: 11% of names with the AI judge on, 45% with it off, the default. Later quarters only need new names reviewed. |

**Verdict.** Medium. The outcome is real but lands once a quarter, and belief starts low. Cheapest lever: belief, through filing links and measured precision. Delay is set by the filing calendar and can't be cut further.

## Recommendation

**Go, scoped to a 2-week build of the matching engine, with the LP read-through as its first use, measured against an answer key.** The stress data is already sold by at least 7 vendors: 9fin flags loans below 90, and PitchBook links BDC loans to company profiles. Matching a client's own messy list to those loans, with proof, is the part not sold off the shelf, and it carries over to other lists and sources. The evidence for that is weaker than first reported: plain matching already gets 94% of loans right. The harder work is companies borrowing under other names and bad filer data. The commercial case turns No-go if 3 LP analysts say PitchBook or 9fin already tells them which of their companies are stressed.

## Open Questions

- Do LP analysts keep a list of underlying companies, or only GP PDFs? If only PDFs, reading them becomes step one.

---

## Appendix A: coverage test (2026-11-01)

| Measure | Result |
|---|---|
| Sample | 291 current companies from 6 sponsor websites: Thoma Bravo, Vista, Genstar, Gryphon, Alpine, Shore |
| BDC data | SEC BDC data sets, Q1 and Q2 2026: 172 filers, about 65,000 holdings per quarter dated that quarter |
| Companies with a usable loan value | 144 of 291 (49%). Thoma Bravo 45/60, Genstar 31/47, Vista 35/60, Alpine 12/30, Gryphon 13/35, Shore 8/59 |
| Companies with any BDC loan, including under other names | 51 of 84 sampled (61%) |
| Loan-level precision of plain name matching | 94.4% on an answer key of 84 companies and 1,028 pairs. Labelled by two Claude labellers, not yet checked by a person |
| Loan-level precision of the matching decisions | 100% (pair-level range 97.7% to 100%), recall 92.8%. Not independent: the judge is also Claude |
| Q2 2026 flags, funded loans | 14 of 144 flagged: debt averages below 90% of par, weighted by loan size. 16 more worth a look: one position is low or fell, or lenders disagree. Script found each flagged company's lowest value in the filing, with no person checking |
| BDC filing lag, Q2 2026 | Median 42 days after quarter end; about day 62 in SEC's monthly data sets (publish date not verified) |

**Limits.** The usable-value count is a lower bound: other names are missed, and 9 of 39 no-hit companies had one. Gaps between lenders are compared only on the same lien and maturity, which may still be different loans. Full results: `outputs/analyses/matching-comparison.md`.

## Appendix B: how it could be delivered

- **Interfaces:** spreadsheet in, same spreadsheet out with columns and filing links. Then a review web app, and a tool AI agents can call (MCP).
- **Matching approaches, compared on one answer key:** (a) name cleaning plus fuzzy matching, the 94% baseline; (b) probabilistic record linkage; (c) embedding search plus a language-model judge.
- **Data cleaning the engine must do:** half the rows are prior-period schedules; cost and principal sometimes don't line up; partly drawn loans read as markdowns; one value was off by a factor of about 1,000.

```
 Your list: 14 of 144 flagged                      Q2 2026 filings (illustrative layout)
 Company    Lenders  Average value  Change  Largest fall
 KnowBe4       9       78.0%        -11.3   Blue Owl fund $47.8M, 88.8 to 77.5   [filing]
 Exabeam      12       86.2%         -3.1   Blue Owl fund $4.8M, 85.0 to 77.5    [filing]
 Needs your review (3): "Orion Group" = Orion Services Group LLC?  [yes] [no]
```

**Sources:** `outputs/analyses/matching-comparison.md`, `data/eval/compare_report.json`, `data/eval/full_results.csv`, `data/eval/flag_sample_checked.csv`, `data/sponsors/README.md`, `outputs/research-synthesis/lp-monitoring-public-signals.md`, EDGAR CIK 1930087 filings gcred-20260331.htm and gcred-20260630.htm.
