# Matching comparison: what works for Lender Watch

**Date:** 2026-11-02 · **Owner:** Alexandre Cela · **Status:** Measured. Labels not yet checked by a person.

**Decision:** match with the exact-name rule, then a language-model judge, then a person for unclear pairs. Drop the scoring model.

## Results

The answer key covers 84 companies and 1,028 candidate pairs, on holdings dated 30 June 2026. Two Claude labellers worked independently and agreed on 98.5%.

| Approach | Loan precision | Loan recall | Companies found | Companies with a wrong loan |
|---|---|---|---|---|
| Plain name search | 94.4% | 90.0% | 44 of 48 | 3 |
| Scoring model (Fellegi-Sunter) | 94.2% | 86.5% | 44 of 48 | 3 |
| Judge on name hits | 100% | 87.6% | 44 of 48 | 0 |
| **Exact-name rule, then judge on wider name hits** | **100%** | **92.8%** | **46 of 48** | **0** |
| Judge on all search results (includes embeddings) | 99.9% | 95.5% | 47 of 48 | 1 |

- **Precision range:** at pair level the chosen approach is 100%, with a 95% range of 97.7% to 100%.
- **Cost:** $0.40 per 100 listed names at batch prices. Judging all search results costs $2.73 and sends 46 of 84 companies to a person, against 3 of 84.
- **Exact-name rule:** 39 pairs skipped the judge, and none was wrong.

## What this means

- **Plain matching is better than first reported.** The 70% in the first draft came from a bug: the cleaner cut "Point C" to "point", which matched "Basis Point". The real gap is about 6 wrong loans in 100.
- **Wrong loans cluster.** They sit in 3 of 84 companies, such as "PROS" pulling in Wheel Pros and "Ascend" pulling in Ascend Learning. For those companies the analyst would raise a false alarm with a GP.
- **The scoring model added nothing.** Name shape can't separate Ascend Partner Services from Ascend Learning. That takes knowing what each business does.
- **Embeddings cost more than they earned.** Wider search found 1 more company and sent 43 more companies to a person.
- **Other names are the main gap.** Web research found 9 of 39 no-hit companies borrowing under another name: Jeppesen Holdings for Jeppesen ForeFlight, LogRhythm for Exabeam, Meta Buyer for Metagenics.

## Recall against all known loans

| Step | Companies found, of 51 known |
|---|---|
| Exact-name rule, then judge on wider name hits | 44 (86%) |
| Plus searching a rare first word (Jeppesen) and automated name research (Exabeam, Metagenics) | 47 (92%), estimated from these cases. Name research isn't in the product |

Automated name research costs about $0.14 a name. In a 20-company test weighted to hard cases, it found 2 of the 9 known names and one unsure case. So it's an option for not-found names, not a default.

## Full list: 291 companies from 6 sponsor websites

| Measure | Result |
|---|---|
| Company has a funded loan with a usable value | 144 (49%): Thoma Bravo 45/60, Genstar 31/47, Vista 35/60, Alpine 12/30, Gryphon 13/35, Shore 8/59 |
| **Flagged: debt averages below 90% of par, weighted by loan size, or that average fell 5 points or more** | **14 of 144 (10%)** |
| Worth a look: one position below 90% or down 5 points or more, or lenders 5 points apart | 16 |
| Flagged companies whose average fell 3 points or more on last quarter | 8 |
| Flagged companies already below 90 last quarter, crossing this quarter, or with no prior value | 9, 2, 3 |
| Names with a match for a person to confirm, AI judge on | 33 of 291 (11%) |
| Names to confirm with the AI judge off, the default | 132 of 291 (45%), 422 questions. Only 51 companies have usable values until they're answered |
| Flagged company's lowest value found next to the name in the filing, by script | 14 of 14. 5 used a common word as the search term |

**Share of companies with a BDC loan of any kind:** 51 of 84 sampled (61%), including loans found through web research. The range is roughly 50% to 71%.

## Data problems the engine handles

1. **Half the rows are old.** Each filing repeats the prior year-end schedule, marked only by a date column. Ignoring it mixed periods and invented falls and gaps.
2. **Amounts that don't line up.** A Goldman row shows 3.28M principal and 10.01M cost for one loan. Rows with cost outside 70% to 115% of principal are excluded and counted.
3. **Partly drawn loans.** Principal can be the full commitment while value covers only the drawn part, which reads as a false markdown.
4. **Scale errors.** A Fortress row shows 5,963 principal against 4.6M fair value.
5. **Repeated rows.** One position can appear more than once, so positions are de-duplicated before counting.
6. **Foreign loans.** Principal is in local currency and value in US dollars, with no currency tag. A Canadian loan at full value still reads about 72% of par, so 123Dentist's 70% says little. Rows with cost below 80% of principal are now left out. This removed Dynamic Connections' lowest row, one of the old flags. Euro loans still pass and read about 108%.
7. **Rejected loans returning.** The engine searched again by name after matching, so Brightview Landscapes came back for BrightView after the judge rejected it. 3 such rows reached the 291-company results. Fixed. The precision table above tests decisions, not this step.

## Limits

- **All labels are Claude's.** So is the judge, so 100% precision isn't independent. A person needs to check `answer-key-spot-check.csv` (50 pairs).
- **20 pairs were left unsure** and are out of the scores. They are mostly short names and deal vehicles, such as ASG and SDC Holdco.
- **The sample is small.** With 84 companies, the rates above can move several points.
- **The filing check covers the value, not the meaning.** A script confirms the number is in the filing, not that the flag predicts anything. With two quarters of data we can't test prediction.
- **4 filers have Q1 rows but no Q2 rows.** All 2026 data sets from April to September are now loaded, covering 172 filers a quarter. Adding them changed no company's flag.
- **Timing:** we read SEC's monthly data sets, so about day 62, not the day 42 filing date. SEC's readme says monthly. Its file dates were reset in October, so the publish date can't be verified from them.
- **Speed:** about 1 second per name, including repeats. The target was under 1 second.
- **Value and stress flags are lender estimates,** not market prices.

**Sources:** `data/eval/compare_report.json`, `data/eval/answer_key.csv`, `data/eval/recall_probe.csv`, `data/eval/alias_test.json`, `data/eval/full_results.csv`, `data/eval/flag_sample_checked.csv`. API spend for all of this: about $6.20.
