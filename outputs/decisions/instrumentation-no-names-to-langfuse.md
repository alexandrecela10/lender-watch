---
decision_id: "ERM-002"
date: "2026-11-07"
product_area: "Entity Reconciliation Machine"
feature: "Usage and quality instrumentation"
prd_stage: "Launch Readiness"
decided_by: "Alexandre Cela (accepted at merge); proposed by the M8 spec session"
status: "active"
supersedes: "intent/instrumentation.md line 41 (names allowed in Langfuse with consent)"
---

# Decision: Send Langfuse counts and verdicts only, never company names

## What was decided

- No company name, prompt, reply or judge reason goes to Langfuse, with the AI judge on or off.
- Each judge call sends Langfuse only counts and flags in (`has_sector`, `has_owner`, `n_examples`), the verdict and stop reason out, and the model, tokens, cost and run id.

## Why

- **Agreeing to the judge isn't agreeing to a second vendor.** A user who turns the judge on agrees to send names to Anthropic. Langfuse is a separate company, so the same consent doesn't cover it.
- **Cost, time and verdict need no names.** The monitoring this feature exists for (judge cost per 100 names, review share, drift) works on counts alone.
- **The ids are names in disguise.** `pair_id` and `entity_id` are short hashes of the company name. Anyone with a candidate list can hash it and see which companies were run, so the ids stay out of Langfuse too.
- **Which companies an LP holds can be confidential,** even when each name is public.

**Example and its counterfactual.** Today, a judge call on "Orion Group" reaches Langfuse as `{"has_sector": true, "has_owner": true, "n_examples": 1}` → `match`. Had we allowed names with consent, the same record would read "Orion Group, Software, owner X", and Langfuse would hold the LP's holdings list.

**Evidence.** On 2026-11-07 a live run made 24 judge calls on the 6 demo names, costing $0.109. Langfuse stored 24 records with 0 company names (`outputs/test-evidence/instrumentation-i5/5-live-run-and-langfuse.jpg`).

## What was NOT chosen

| Alternative | Why rejected |
|---|---|
| Send names to Langfuse when the person agreed to the judge (the intent's first draft) | Consent covered Anthropic only (spec concern 1) |
| Send names but hash them | Short hashes can be reversed from a candidate list (spec concern 3) |
| Send the judge's reason | It quotes the filing row, which names the borrower (spec concern 8) |
| Use Langfuse's automatic capture (`@observe`) | It records function arguments, which are company names |
| Let Langfuse export every AI-related trace in the process | By default it also sends other libraries' records, which can contain prompts. It now exports its own records only |

## Consequences

**This decision enables:**
- Turning monitoring on for any customer list without a new privacy review.
- Measuring cost per 100 names and the share needing review, from local records or Langfuse.

**This decision prevents:**
- Seeing in Langfuse which company a slow or costly call was about. To debug one call, match its run id to the local log on the machine that ran it.
- Judging answer quality from Langfuse alone: it holds the verdict but not the reason.

**Reversibility:** reversible as code, one-way as data. Allowing names later is a small code change, but a name already sent can't be recalled from Langfuse.

## Open questions remaining

- [ ] Should a run's judge calls appear as one trace in Langfuse, not 24? Today each call is its own trace, linked by the shared `request_id`. @Alexandre Cela

## Review trigger

- Revisit if a customer asks for name-level debugging and signs a data agreement covering Langfuse.
- Revisit if the judge moves to a model inside the LP's own systems.
- Otherwise permanent.

---

*Source: `specs/instrumentation.md` concerns 1, 3, 8 and 9; `plans/instrumentation.md` "Options not chosen"; commits `c49be61` (I3) and `f3eab28` (evidence).*
*Pain is inferred from public signals. No LP analyst has been interviewed.*
*File to `context-library/decisions/instrumentation-no-names-to-langfuse.md` once ratified; Alexandre moves it.*
