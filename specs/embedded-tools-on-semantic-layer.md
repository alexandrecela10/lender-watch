# Spec: embedded tools on agreed definitions (prototype)

Source: `intent/embedded-tools-on-semantic-layer.md` (commit `f0583fd`, approved 2026-11-21). Status: draft, 2026-11-21. Fresh review done; its 12 concerns are resolved below. Pending Alexandre's approval, including two rule changes (concerns 8 and 13).
Evidence: public lender filings, and synthetic data this build generates. No LP or GP analyst has been interviewed. The pain is inferred.
Kind: prototype. Runs on this computer only, on the public sample. Never on the hosted Lender Watch address.

## Bottom line

- One new tool, `get_measure`, answers an agreed measure for a list of companies and a quarter. In Excel: `=LW.MEASURE(name, A2:A10, [as_of])`.
- Six measures, each written once in `semantic/measures.yaml` with plain words, an owner and a version. Code computes them. The AI never makes a number.
- A synthetic investor holds 60 companies through 8 funds: 20 real companies with real lender data, and 40 invented ones.
- A letter reader turns a manager's letter into proposed events. Nothing counts until a person confirms it.
- A change explainer says why a measure moved between the two quarters held. Code computes the parts and fills every number into the sentence; the model only chooses the words.
- Every value says where it came from: a filing, or "synthetic". The investor's own records may sit beside a real company's name, always labelled synthetic. Nothing invented about a real company itself: no revenue, debt, value or letter.

## Problems this solves

| Problem | Today | Hypothesis (if/then/because) | Success metric (target) | Expected impact |
|---|---|---|---|---|
| Lender stress can't be tied to our money | No holdings data | If the synthetic investor's look-through cost is joined to Lender Watch flags by company, then "how much of our cost sits in flagged companies" has one answer, because the join uses Lender Watch's own match | Measure 3 returns a row with sources for each of the 60 companies: 60 of 60 | Shows the join works. Real use needs real holdings |
| Each new measure needs new code in the tool | Flag rules are constants, no owner or version | If measures are definitions the tool looks up by name, then adding one needs a definition and a function, not a new tool | Measures defined outside the tool, with owner and version: 6. Time to add a seventh: measured once | New questions cost a definition, not a release |
| Excel and Claude could disagree | Unobserved | If both call one function, then results match | Same measure, companies and quarter through `/api/measure` and `get_measure`: identical for all 6 | Front ends can't drift apart |
| News in letters reaches no number | Retyped by hand, rate unobserved | If a model proposes dated events with the exact sentence, and a person confirms, then confirmed events change measures without retyping | Events found and wrong events, scored against the generator's truth on 20 letters. No target until the first run | Shows the rate |
| A wrong event could change a number | No events | If an event counts only after a person confirms it, then no model mistake reaches a measure | Measures changed by an unconfirmed event: 0 | The model can be wrong without harm |
| Moves between quarters are explained by hand | Unobserved | If code computes parts that add up exactly, then the explanation is checkable | Explanations whose unrounded parts sum to the total: all | The analyst can check the sentence |
| The explainer could invent a number or a direction | No explainer | If the model writes words around placeholders and code fills every number and direction, then no invented figure reaches the analyst | Sentences with a number or direction not from code: 0 | The sentence can't misstate a figure |

**Must not get worse:** everything in Lender Watch's spec: precision 1.000 and recall 0.936, filing link on every real value, AI judge off by default, `make test`, `make lint`, `make evals` green. `check_lenders` results and `data_version` unchanged. The hosted tool list stays exactly `check_lenders` and `confirm_match`, and the hosted service reads no synthetic file. Invented facts about a real company: 0. Values from a synthetic source not labelled synthetic: 0. Real firm names in synthetic investor, fund or invented company names: 0.

**Not tackled:**
- Deal flow. Missing: documents and a pipeline.
- Today's value of real companies. Missing: real private data. Exposure uses the investor's cost.
- More than one quarter pair. The public sample holds 2026-03-31 and 2026-06-30 only, so measure 2 and every explanation cover March to June.
- Hosting the prototype. By decision.
- Letters about real companies. By the rule on invented facts.
- Letter-reading in Excel. Claude only, through the local tools.

## Concerns and resolutions

"Fresh" means the separate review of 2026-11-21 with no access to this conversation.

| # | Concern | Raised by | Decision | Why |
|---|---|---|---|---|
| 1 | Letters written from a template would make reading trivial; letters written freely may drift from their events. | Spec | Superseded by concern 9. | |
| 2 | Measure 3 on a real company needs a dollar figure. | Intent review | Use the investor's look-through cost: its own records, never a value for the company. Rule wording in concern 8. | A fact about the invented investor, not the real company. |
| 3 | Measures 5 and 6 need private data that only exists for invented companies. | Spec | Each measure declares `applies_to`. A real company gets "not available for real companies", never a number. | No invented fact about a real company, by construction. |
| 4 | Invented companies need lender marks for flags and measure 6. | Spec | Section 1: synthetic lender rows, kept apart from real holdings. | One flag rule for both kinds. |
| 5 | A new tool changes what Claude sees. | Spec | New tools on the local server only. Test: hosted list unchanged. The tool-choice eval uses the hosted list. | The approved product stays as approved. |
| 6 | The reader and the explainer call Anthropic. | Spec | Off by default; on with `--use-ai` or `LW_PROTOTYPE_AI=1`. They send synthetic letters and synthetic or public numbers only. | Same rule as the judge. |
| 7 | A write-down should count from when we learned it. | Spec | Section 2, measure 6 rule. | Same rule as the earlier 60-question test. |
| 8 | Measures 3 and 4 put a synthetic cost beside a real company's name; nothing tests the label. | Fresh | The rule is now: the investor's own records may sit beside a real name; each value carries its own source with `kind: filing` or `kind: synthetic`; any row using a synthetic source has `synthetic: true`, and the Excel output adds a "Source" column reading "synthetic" or "filing". Checks 3 and 16. The rule is added to `data-handling` check 1 for Alexandre's approval. | States what's allowed, and makes the label testable. |
| 9 | A model writing the letters breaks reproducibility, needs its own exception, and may make the reader look better than it is. | Fresh | Letters are built by code from events: 6 phrasings per event type, a date and amount in one canonical format, and 2 to 4 sentences of unrelated commentary drawn from a pool. No model writes letters. | Reproducible from the seed, no new outside call, and the reader isn't reading its own prose. Limit: templated prose is easier than real letters. Stated with every result. |
| 10 | Measure 2 isn't measure 1 now minus measure 1 before. Two quarters limit explanation. | Fresh | Measure 2 is Lender Watch's `weighted_change`: paired loans only, and "not enough paired loans" when it returns None. Measures 1, 2 and 5 have no explainer. Explanations cover March to June 2026 only. | Matches Lender Watch exactly. Avoids a by-loan formula with loans entering and leaving. |
| 11 | Synthetic lender rows weren't specified, and mixing them into real holdings would change Lender Watch. | Fresh | Section 1 lists the 12 columns and rules. Stored apart, with `company_id`. Passed straight to `usable`, `facts_for` and `flags_for`, never to `Engine.holdings` or `resolve_entity`. `inlineurl` is `synthetic:holdings:<row>`. Test: `check_lenders` and `data_version` unchanged. | Lender Watch can't find "Synthetic Company 01". |
| 12 | Results depend on which holdings file loads and on saved answers. | Fresh | The prototype pins `data/public/holdings.parquet` and its own copy of the seed answers. The 20 real companies are committed with the `data_version`. Test: all 20 resolve as `matched`, with loans in both quarters. | Stable results, the same on any computer. |
| 13 | `api-and-logging` rule 4 and `data-handling` checks 1 to 3 assume public data with filing links only. | Fresh | Both skills gain one line: inside the prototype paths (`erm/semantic.py`, `erm/letters.py`, `data/synthetic/`, `semantic/`), a value may carry a synthetic source instead of a filing link, always labelled. For Alexandre's approval. | Rules stay honest about what the prototype does. |
| 14 | Measures 3 and 4 left choices open. | Fresh | Answered in section 2. | One answer per question. |
| 15 | Measure 6, events and measure 5 weren't defined to one answer. | Fresh | Section 2. Event types cut to two: `write_down` (changes measure 6) and `covenant_breach` (changes nothing; tests the reader). | Every event that exists has a defined effect. |
| 16 | Letter scoring was undefined. | Fresh | Section 4 match rule. Check 15: a letter names no company or amount beyond its own events. | Fair scores. |
| 17 | The explainer had no formulas, and rounding could break the sum. | Fresh | Section 5 formulas. Unrounded parts sum to the total; any rounding difference is shown as its own part. | The sum check always means something. |
| 18 | A number check on free text is weak. | Fresh | The model returns words with placeholders such as `{part_2.amount}` and `{part_2.direction}`. Code fills them. A sentence with any digit or direction word outside a placeholder is rejected, and the template is used. | It can't misstate a figure or a direction. |
| 19 | No storage or surface for events and explanations; no logging rule; the hosted code path. | Fresh | Section 3: local tools and an events store. Logs: JSON with request id, counts only, never letter text or company names. `/api/measure` exists only with sign-in off, and the semantic module loads on first use. Test: the hosted service starts without reading `data/synthetic/`. | Every function is reachable, logged safely, and kept out of the hosted path. |
| 20 | The generator had no rules on ownership or debt. | Fresh | Section 1 rules, each tested. | No impossible portfolio. |

## 1. Synthetic data

`scripts/make_synthetic.py --seed 2026` writes `data/synthetic/`, committed. Every table has `synthetic: true` on every row.

| Table | Holds |
|---|---|
| `investor.csv` | One row: "Synthetic Pension Plan" |
| `funds.csv` | "Synthetic Fund 1" to "Synthetic Fund 8". Funds 7 and 8 are funds of funds |
| `fund_stakes.csv` | Owner, fund, share. The investor owns funds; funds 7 and 8 own funds 1 to 6 only |
| `positions.csv` | Fund, company id, quarter, cost in US dollars |
| `companies.csv` | 60 rows: `company_id`, `name`, `kind` (`real` or `invented`). Real names are the ones Lender Watch matches; invented ones are "Synthetic Company 01" to "40" |
| `real_companies.json` | The 20 real names, with the `data_version` they were chosen on |
| `financials.csv` | Invented companies only: revenue, EBITDA, net debt, per quarter |
| `manager_values.csv` | Invented companies only: the manager's equity value as % of cost, per quarter, and the date reported |
| `holdings.parquet` | Invented companies only: lender rows (below) |
| `events.csv` | Truth for letters: id, company id, type, size, effective date, received date, letter number |
| `letters/NN.md` | 20 letters built by code from the events (concern 9) |

**Synthetic lender rows:** the 12 columns of `data/public/holdings.parquet` (`lender, period, raw_text, principal, fair_value, lien, maturity, pik_rate, pct_par, excluded_reason, inlineurl, filed`) plus `company_id`. `excluded_reason` is "". `pct_par` equals `fair_value / principal × 100`. Each loan appears in both quarters, with principal changing less than 25%, so Lender Watch pairs it. `raw_text` names the invented company. `inlineurl` is `synthetic:holdings:<row>`. Lenders are "Synthetic Lender A" to "E".

**Real companies:** chosen once from `data/demo/sample_list.csv` and `data/sponsors/sponsor_portfolios.csv`: those Lender Watch resolves as `matched`, with no item to confirm and usable loans in both quarters, on the public sample with AI off. At least 3 must be flagged at 2026-06-30.

**Generator rules, each tested:**
- No fund of funds holds another fund of funds, so there are no loops.
- Owners' shares of each fund sum to at most 100%.
- An invented company's net debt is at least the principal of its synthetic loans.
- Every invented company has positive revenue. About a tenth have EBITDA at or below zero, to test measure 5's rule.
- Every company is held by at least one fund. At least 5 are held through more than one path.

## 2. Measures

`semantic/measures.yaml`: `id`, `name`, `definition` (plain words), `unit`, `applies_to` (`real`, `invented` or `both`), `owner` ("Alexandre (acting owner)"), `version`, `compute` (a function in `erm/semantic.py`), `explain` (`none`, `company` or `component`).

**Company names in a request:** matched to `companies.csv` by exact name, ignoring case, or by `company_id`. Anything else gives "not in the synthetic portfolio".

**Every row returned:** `company`, `company_id`, `value` or `not_available` with a reason, `unit`, `measure`, `version`, `as_of`, `synthetic` (true if any source is synthetic), and `sources`, each with `kind` (`filing` or `synthetic`) and a link or `synthetic:<table>:<row>`.

| # | id | Definition | applies_to | Explain |
|---|---|---|---|---|
| 1 | `lender_value` | Lenders' value of the debt as % of amount owed, averaged by loan size: Lender Watch's `weighted_pct_par` | both | none |
| 2 | `lender_change` | Change in that average on loans held in both quarters, in points: Lender Watch's `weighted_change`. "Not enough paired loans" when it has none. Not available at 2026-03-31 | both | none |
| 3 | `cost_in_flagged` | Our look-through cost in the company if Lender Watch flags it (level "flagged" only), else 0 | both | company |
| 4 | `share_cost_flagged` | Measure 3 divided by our total look-through cost across all 60 companies at that quarter | both | company |
| 5 | `debt_to_ebitda` | Net debt divided by the quarter's EBITDA times four. "Not meaningful" when EBITDA is at or below zero | invented | none |
| 6 | `manager_lender_gap` | Manager's equity value as % of cost, after confirmed write-downs, minus lenders' debt value as % of amount owed, in points | invented | component |

**Look-through cost:** the sum over every ownership path of the product of shares along the path, times the fund's cost in the company at that quarter.
Example and counterfactual: we own 20% of Synthetic Fund 7, which owns 10% of Synthetic Fund 3, which paid $40m for a company. Our look-through cost is $0.8m. Counting the fund's whole $40m would overstate it 50 times, the error of setup A in the earlier test.

**Measures 3 and 4, in detail:**
- One row per requested company, plus a `total` row that sums the company rows.
- A company Lender Watch can't settle (needs a person's answer, or no usable loans) gets "not checked", stays out of the numerator, and is counted in the total row's `not_checked`.
- A value of 0 has two sources: the flag's filing (real) or synthetic lender rows (invented), and the cost rows.
- Measure 4's denominator is always the whole portfolio, so a company's share doesn't depend on which others were asked for.

**Measure 6, in detail:**
- Manager value at a quarter: the latest row in `manager_values.csv` with that quarter.
- A confirmed `write_down` event sets the manager value to its size, a % of cost, when it was received after that row was reported and on or before the quarter-end.
- A `manager_values.csv` row reported after the write-down already includes it, so the event no longer applies. No double counting.
- `covenant_breach` events change no measure.
- `received` comes from `events.csv`, the letter's own date, never from the model.

## 3. Tools, routes and storage

All local, on the public sample. None on the hosted service.

| Where | Name | Does |
|---|---|---|
| Claude, local server | `get_measure(measure, companies, as_of?)` | Measure rows. Its description lists measures by id and plain name, read from the file |
| Claude, local server | `read_letter(letter)` | Proposes events from a letter's text. Needs AI on |
| Claude, local server | `confirm_event(event_id, yes)` | A person's answer on a proposed event |
| Claude, local server | `explain_change(measure, companies)` | The parts and the sentence, March to June 2026 |
| Excel | `=LW.MEASURE(name, A2:A10, [as_of])` | Through `/api/measure`. Spills value, unit, and Source ("filing" or "synthetic") |
| Service, sign-in off only | `/api/measure` | Same function as `get_measure` |

**Storage:** proposed and confirmed events in `prototype.sqlite`, under the local data folder (`LW_DATA_DIR`, default `~/.erm/service`). Columns: id, letter, company id, type, size, effective, received, quote, status (`proposed`, `confirmed`, `rejected`), decided at.

**Logs:** JSON, one request id per call, counts only: measure id, companies in, rows out, events proposed or confirmed. Never letter text, a quote or a company name.

## 4. Letter reader

- `erm/letters.py`, `read_letter(text, client)`: `claude-opus-5-5` with structured output. Each proposal has company, type, size, effective date and quote. `received` is the letter's date.
- Code drops a proposal whose quote isn't in the letter, after normalising spaces and quote marks.
- Proposals are stored as `proposed`. Only `confirmed` events change measures.

**Scoring** (`eval/letters.py`, by hand, AI on):
- **Found:** a proposal matches a true event when company id and type are equal, the effective date is exact, and the size is within 0.5 points. One proposal matches at most one event.
- **Wrong:** a proposal that matches no event.
- **Field accuracy:** for found events, each field right or wrong.
- Results always say "templated letters", because they are easier than real ones.

## 5. Change explainer

`explain(measure, companies)`, March to June 2026. Code computes the parts:

- **Measure 3**, per company: `cost_in_flagged(June) − cost_in_flagged(March)`, split into:
  - Newly flagged: June cost, when flagged in June and not in March.
  - No longer flagged: minus March cost, when flagged in March and not in June.
  - Cost moved while flagged: June cost minus March cost, when flagged in both.
- **Measure 4**, per company: `m3(June)/total(June) − m3(March)/total(March)`.
- **Measure 6**, per company:
  - Manager value moved (before write-downs).
  - Write-down applied.
  - Lenders' value moved, with the sign flipped.
- **Totals:** unrounded parts sum to the total change, checked in code. A rounding difference in what's shown appears as its own part, "rounding".
- **Sentence:** AI on: the model gets part ids and labels, never the numbers, and returns words with placeholders. Code fills each placeholder with the formatted amount or direction ("rose", "fell"). The sentence is rejected if any digit or direction word sits outside a placeholder, or a placeholder names no part; then the template is used. AI off: always the template.

## Acceptance checks

**Automated, in `make test`:**
1. The generator with seed 2026 reproduces every committed file in `data/synthetic/` byte for byte, letters included.
2. No real company has a row in `financials.csv`, `manager_values.csv`, synthetic `holdings.parquet` or `events.csv`, or appears in a letter.
3. Every synthetic table has `synthetic` true on every row. Investor, fund, lender and invented company names match no firm or company in `data/sponsors/` or the public lender data.
4. Every generator rule in section 1 holds.
5. `real_companies.json` names 20 companies, each `matched` with loans in both quarters on its recorded `data_version`; at least 3 flagged at 2026-06-30.
6. `semantic/measures.yaml` loads; every measure has every field, and its `compute` exists.
7. The look-through example gives $0.8m.
8. Measure 3 returns a row with sources for all 60 companies, and a total that equals the sum of the rows.
9. A measure for invented companies, asked for a real company, returns "not available for real companies" and no number.
10. Every measure gives identical rows through `/api/measure` and `get_measure`.
11. Measures 1 and 2 for each real company equal Lender Watch's `weighted_pct_par` and `weighted_change`.
12. `check_lenders` results and `data_version` are the same with and without the synthetic data loaded.
13. An unconfirmed event changes no measure. A confirmed write-down changes measure 6 at the quarter-end after it was received, and not once a later manager value includes it.
14. A proposal whose quote isn't in the letter is dropped.
15. Each letter states its events' company, date and size in the canonical format, and names no other company or amount.
16. Every row with a synthetic source has `synthetic` true, and the Excel output's Source column reads "synthetic" on it.
17. For measures 3, 4 and 6 and every company, the unrounded parts sum to the total.
18. A sentence with a digit or direction word outside a placeholder is rejected, and the template is used.
19. The hosted tool list is exactly `check_lenders` and `confirm_match`. With sign-in on, `/api/measure` isn't served and the service starts without reading `data/synthetic/`.
20. No log line from these tests holds a letter's text, a quote or a company name.

**Live, by hand, with Alexandre's key, AI on:**
21. `eval/letters.py` on the 20 letters: events found, wrong events, fields right, cost and time. No target on the first run.
22. Ten explanations: every sentence passes check 18's rule, or falls back.

**Measured once:**
- Time to add a seventh measure, from a blank entry to a passing test.
