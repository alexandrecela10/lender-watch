# Lender Watch: LP credit read-through

**Stage:** Planning Review · **Last updated:** 2026-11-02 · **Owner:** Alexandre Cela · **Status:** Draft
**Source:** `outputs/opportunity-analyses/lp-credit-readthrough-opportunity.md` (Go). Decision: ERM-001.
**Evidence:** public filings and commentary. No LP interviewed yet, so the pain is inferred.
**Corrected 2026-11-02:** re-measured after two rounds of fixes, the second from the review panel. See `outputs/prds/lp-credit-readthrough-planning-review-review-synthesis.md`.

## What we're building

**Lender Watch** is a quarterly check for LP and fund-of-funds analysts.

- **Goes in:** a spreadsheet of company names, written the way the LP writes them.
- **Comes out:** the same spreadsheet plus, per company, each BDC lender's loan value this quarter and last, flags, and a link to each filing row.
- **Gain:** the analyst sees which companies their lenders have marked down about day 62 after quarter end, as built. GP reports are due day 60 to 120, so the lead is up to about 2 months, and none against the earliest reports.
- **Can't do yet:** cover lenders that don't file publicly, read filings the day they land (day 42), read GP PDFs, compare with GP equity values, or say whether a flag predicts anything.

Matching doesn't depend on the source, and any list of names works. No second source has been added, so reuse across sources is untested.

## Hypothesis

| # | Problem | Today | Hypothesis | Success metric (target) | Expected impact | Value opportunity per LP per year (cases × today × gain × value per unit) |
|---|---|---|---|---|---|---|
| 1 | Finding a company's loans | Manual search. A matched company sits in a median of 4 BDC funds under 5 descriptions (observed) | If the engine searches every filer for each name, then the full list is covered each quarter, because search stops being manual | Companies found, of those known to have loans: ≥ 90% | Full list covered. 49% of 291 sampled companies have a loan with a usable value (observed). Companies found: 86%, below target. About 92% if name research were added; it isn't in the product | **Productivity: about $22k.** 980 company-quarters × 10 min to find by hand × 90% saved × $150/hour. Mostly coverage gained, not cost saved: analysts don't search every name today |
| 2 | Wrong matches | Plain name matching: 94% of loans found are right, with errors clustered in 3 of 84 companies (observed) | If a language model judges unclear names on context and the rest go to a person once, then name clashes drop out, because "Apex Group" no longer pulls in Apex Dental | Loan-level precision: ≥ 97% | Wrong loans fall from 6 in 100 to 0 in the test, not yet checked by a person (observed) | **Productivity: about $11k.** 980 company-quarters × 5 min checking matches × 90% saved × $150/hour. Same caveat, and matches are confirmed once, not each quarter |
| 3 | Seeing lender markdowns early | Hand checks on a few names (assumed) | If the engine compares loans across lenders and quarters, weighted by size, then markdowns show about day 62 as built (day 42 if it read filings directly, not built), because BDCs report before most GP reports | Flags a person confirms against the filing: ≥ 90% | 14 of 144 companies flagged in Q2 2026 (observed). 8 fell 3 points or more; 9 were already below 90 last quarter. Whether a flag predicts a GP markdown is unobserved | **Alpha (loss avoided): about $14k to $240k, all assumed.** High: 8 companies later marked down × caught early 10% → 90% × $37.5k ($5M × 15% markdown × 5% chance a decision is priced in the window). Low: 2.4 companies × same gain × $7.5k (1% chance) |

**Must not get worse:** values shown without a filing link: 0.

## Strategic fit

There's no strategy document yet, so fit is judged against the project's goals: a tool someone uses, learning the technology, a case study, and an engine reusable elsewhere.

**Why now:** SEC's BDC data sets give every holding in tagged form, so we can build on data instead of parsing PDFs. ILPA's portfolio company template refresh, due January 2027, may also make company lists easier for LPs to hold (to test in interviews).

**Impact sizing for one assumed LP**

| Step | Companies | Basis |
|---|---|---|
| Underlying companies | 500 | Assumed |
| With BDC loans | 245 | 49%, observed |
| Flagged | 24 | 10% (14 of 144), one quarter's snapshot used as the yearly count: the yearly rate is unobserved |
| Later marked down by the GP | 8, or 2.4 in the low case | 1 in 3, or 1 in 10, both assumed |

| Assumption | Confidence | How we check it |
|---|---|---|
| LPs hold a usable company list | Medium | Interviews |
| A flag leads to a decision in the window (5%, or 1%) | Low | Interviews. A re-up or co-invest sheds no existing exposure, and LPs sell fund stakes, not single companies, so even 1% may be high |
| 1 in 3 flags precede a GP markdown | Low | Interviews; a back-test on older SEC data sets |
| Vendors don't already answer this for an LP's own list | Medium | Interviews; a PitchBook demo |
| Exposure $5M, markdown 15%, early catch 10% → 90% | Low | Interviews |

**Result:** about $33k of analyst time, mostly coverage rather than savings, and about $14k to $240k of avoided loss per LP a year, all assumed. The case rests on the least proven line, and no one has been asked what they'd pay.

**Alternatives rejected:** see ERM-001.

## Value Equation (Hormozi)

| Factor | This solution |
|---|---|
| **Dream outcome** | "I walk into the GP meeting knowing which of our companies their lenders have already marked down, with the filing to show." |
| **Perceived likelihood** | Low before first use. Analysts distrust automatic matching, and one wrong loan means a false alarm with a GP. A filing link on every value and a published precision figure are what earn belief. |
| **Time delay** | Results the day the list is loaded. The benefit lands at the next quarterly review, up to 90 days later. |
| **Effort & sacrifice** | Export the company list, if they keep one (untested). Confirm unclear matches once: 11% of names with the AI judge on, 45% with it off, the default. Later quarters only need new names reviewed. |

**Verdict.** Medium. Cheapest lever: belief, through filing links and measured precision.

## Non-goals

- **Lender vs GP equity value:** needs private GP reports.
- **Lenders that don't file, such as banks:** no public data. Only 8 of 59 Shore Capital companies show up.
- **Default prediction:** v1 reports facts and changes. We have no outcome data to test a prediction.
- **Reading GP PDFs:** added only if interviews show LPs hold no list.
- **Logins, scheduling, multi-user:** not needed to test the value.

**Trade-off:** we favour precision over recall. A missed loan is a gap the analyst can check; a wrong loan is a false alarm raised with a GP.

## Success metrics

**Primary:** loan-level precision on the answer key, from 94.4% to ≥ 97% by 16 November 2026. Measured: 100%, recall 92.8%. Claude wrote the labels and Claude is the judge, so this isn't independent until a person checks them.

| Metric | Baseline | Target |
|---|---|---|
| Companies found, of those known to have loans | 86% measured, target missed. About 92% with name research, which isn't in the product | ≥ 90% |
| Flagged company's lowest value found in the filing | 14 of 14 by script, no person; 5 used a common search word | ≥ 90% confirmed by a person |
| Names needing human review (guardrail) | 33 of 291 (11%) with the AI judge; 132 of 291 (45%) with it off, the default | ≤ 15%, once each. Missed with the judge off |
| Values without a filing link (guardrail) | n/a | 0 |

**Kill criteria**
- 3 LP analysts say PitchBook or 9fin already tells them which of their companies are stressed: stop the commercial case, keep the engine for side projects.
- Precision stays below 97% after 2 weeks: no flags go to users, and we rework matching.

## Rollout

- **Week 1:** clean the data, build the answer key, compare 3 matching approaches. **Pass:** one approach reaches ≥ 97% precision.
- **Week 2:** spreadsheet in and out, review app, agent tool, flags. **Pass:** all metrics above met on the 291-company list.
- **Then:** 2 or 3 LP analysts test it on their own list, on their machine. The AI judge stays off unless they turn it on, because it sends names to Anthropic. **Pass:** each names a past decision a flag would have changed.

**Rollback:** if flag confirmation falls below 90%, show values and links only, without flags.

## AI behavior contract

| Dimension | Specification |
|---|---|
| **Task** | Judge whether a listed company and a BDC holding are the same company, and say why |
| **Inputs** | Listed name, sector, sponsor if given; holding text, BDC industry, loan terms. Sent to Anthropic, so it runs only if the user turns it on |
| **Output** | `match`, `no_match` or `unsure`, plus a reason quoting the holding text |
| **Only runs on** | Pairs with a name hit that the exact-name rule doesn't settle |
| **Disallowed** | Producing or changing any loan value; using outside knowledge as evidence without marking it |
| **Checked by** | The answer key on every prompt change; a person for every `unsure` |
| **Model** | Claude Opus 5.5 at low effort; server-side refusal fallback on live calls. A cheaper model isn't tested yet. |

| Listed name | BDC holding text | Expected | Why |
|---|---|---|---|
| Anaplan | Anaplan, Inc. | `match` | Same name |
| Infoblox | Delta TopCo, Inc. (dba Infoblox, Inc.) | `match` | Trade name stated |
| Foundation | Superman Holdings, LLC (dba Foundation Software) | `match`, if the list says construction software | Trade name fits sector |
| Foundation | Foundation Risk Partners, Corp. (insurance) | `no_match` | Different business |
| Apex Group | Apex Dental Partners, LLC | `no_match` | Different business |
| Point C | Basis Point Spread Above Index | `no_match` | Common words, not a company |
| Orion Group | Orion Services Group LLC | `unsure` | Could be the same; a person decides |

**Fallbacks:** a failed or unclear judgment becomes `unsure` and goes to review. It's never auto-matched.

## Risks

| Risk | Detection | Fallback |
|---|---|---|
| Wrong match causes a false alarm | Precision on answer key; review decisions | Raise the auto-match bar; send more to review |
| Different loans read as a lender disagreement | Bonterra-style gaps in testing | Compare only the same lien and maturity; otherwise label "different loans" |
| Bad filer data (duplicates, scale errors) | Row checks, plausibility range | Left out, counted per company, with a filing link |
| Foreign loans: principal in local currency, cost and value in US dollars, so a Canadian loan reads about 72% | Cost below 80% of principal | Left out as above. Euro loans still pass and read about 108%, which lifts an average slightly |
| Filer tags or formats change | Row counts per filer each month (not built) | Flag the filer as not updated |
| Marks read as market prices | User testing | State "lender's estimate" next to values |
| Statements about named companies | Wording review; a person checks values before any public use | Say "lender's value fell X", never "stressed". A lawyer should review before any customer use |

## Open questions

- [ ] Do LPs hold a list, or only GP PDFs? Owner: Alexandre (interviews)
- [ ] What are the real alpha inputs? Owner: Alexandre (interviews)
- [ ] Does a PitchBook or 9fin subscription already do this for a client's own list? Owner: Alexandre (demo, interviews)
- [ ] Keep the name "Lender Watch"? Other options: "Lender Stress Check" (says the job), "Portfolio Lender Monitor" (says the scope). Owner: Alexandre
- [ ] Does the LP's fund agreement allow company names to go to an outside AI service? Owner: Alexandre, with a lawyer

---

## Appendix A: engine contracts

| Call | Input | Output |
|---|---|---|
| `resolve_entity(name, context?)` | Name as written; optional sector, sponsor | `entity_id`, `canonical_name`, `confidence`, candidates with reasons, `status`: matched, needs_review or not_found |
| `gather_facts(name, context?)` | Raw name; optional sector, sponsor | Flags and fact rows: value, period, lender, loan, `filing_url`, `filing_row`. Quarter is fixed in code |
| `enrich_table(file, name_column, out)` | Any spreadsheet with names | Same spreadsheet plus lender columns, and an All loans sheet with one filing link per loan |
| `review(pair_id, decision)` | Accept or reject | Saved; overrides automation; never asked again |

SEC BDC data is the only source. A second source would need a connector interface, which doesn't exist yet. Moving to a new quarter means a manual download and changing two dates in code.

## Appendix B: matching approaches compared

| Approach | What it tests |
|---|---|
| Name cleaning plus fuzzy match | The baseline: 94.4% loan precision |
| Probabilistic record linkage | Whether sector and loan terms lift precision without a language model |
| Embedding search plus a language-model judge | Whether renames and trade names are found, at what cost per name |

Each approach reports precision, recall, review load and cost per 100 names on the same answer key. Chosen: an exact-name rule, then the language-model judge, then a person. The scoring model added nothing, and wider search added review load for little gain. Results: `outputs/analyses/matching-comparison.md`.

## Appendix C: defaults taken with the PM away

- **Stage:** Planning Review, because the opportunity analysis already answers the kickoff questions.
- **Working name:** Lender Watch.
- **First interface:** spreadsheet, since that's where analysts already work.
- **Deadline:** 16 November 2026, 2 weeks from the start of work.
- **Review load target:** ≤ 15% of names, from the opportunity analysis estimate.
- **Not filled:** `context-library/business-info-template.md` and `context-library/strategy/` are empty.
