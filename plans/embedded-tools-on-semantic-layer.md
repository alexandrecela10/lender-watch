# Plan: embedded tools on agreed definitions (prototype)

Date: 2026-11-21. Owner: Alexandre. Build: one step per commit, on branch `claude/embedded-tools-prototype`.
Source: `specs/embedded-tools-on-semantic-layer.md` (approved 2026-11-21, commit `90ee2c5`), from `intent/embedded-tools-on-semantic-layer.md` (commit `f0583fd`).
Evidence: public lender filings and synthetic data. No analyst has been interviewed. The pain is inferred.

## Summary

- 7 steps. Steps 1 to 5 are mine and make no outside call. Step 6 needs Alexandre's key for about $1 of AI calls. Step 7 is the check and the pull request.
- Step 1 builds the synthetic portfolio, and a test that it rebuilds exactly from its seed.
- Step 2 writes the six measures and the one function behind them. It's the riskiest step for Lender Watch, because it must use Lender Watch's flag code without changing Lender Watch.
- Step 3 puts the measures in Claude and Excel, on this computer only.
- Step 4 adds the letter reader and the person's confirmation. Step 5 adds the explainer.
- `make evals` and Lender Watch's own tests run at every step. Any change to `check_lenders` results stops the step.

## Order

### P1. Synthetic portfolio

Files: `scripts/make_synthetic.py` (new), `data/synthetic/` (new: `investor.csv`, `funds.csv`, `fund_stakes.csv`, `positions.csv`, `companies.csv`, `real_companies.json`, `financials.csv`, `manager_values.csv`, `holdings.parquet`, `events.csv`, `letters/01.md` to `20.md`), `tests/test_synthetic.py` (new).
- Seeded generator, standard library and pandas only. Letters from 6 phrasings per event type, plus unrelated commentary.
- The 20 real companies are chosen by running Lender Watch on the public sample with AI off, and recorded with the `data_version`.
- Parquet is written with fixed settings so the bytes repeat.

Exit criteria
- Tests for spec checks 1 to 5 and 15.
- `make test`, `make lint` and `make evals` green.
- Commit: `feat(prototype): synthetic portfolio from a fixed seed`.

### P2. Measures

Files: `semantic/measures.yaml` (new), `erm/semantic.py` (new), `tests/test_semantic.py` (new), `.claude/skills/data-handling/SKILL.md`, `.claude/skills/api-and-logging/SKILL.md`.
- Loads the definitions and checks them. Look-through cost over every ownership path.
- Real companies: Lender Watch's `Engine` on `data/public/holdings.parquet` with a private copy of the seed answers, AI off. Invented companies: synthetic lender rows passed straight to `usable`, `facts_for` and `flags_for`.
- `get_measure(measure, companies, as_of)` returns the row shape in spec section 2, plus a total row for measures 3 and 4.
- The two skills gain the one-line rule for synthetic sources in prototype paths (spec concerns 8 and 13).

Exit criteria
- Tests for spec checks 6 to 9, 11, 12 and 16 (the row part).
- `make evals` unchanged. `make test`, `make lint` green.
- Commit: `feat(prototype): six agreed measures behind one function`.

### P3. Claude and Excel

Files: `erm/prototype_tools.py` (new), `erm/mcp_server.py`, `erm/service.py`, `app/desk/excel/functions.json`, `app/desk/excel/functions.js`, `app/desk/excel/core.js`, `tests/test_semantic.py`, `tests/test_service.py`, `tests/excel_addin_check.cjs`.
- `get_measure` on the local server only. Its description lists measures from the file.
- `/api/measure` only when sign-in is off. The service loads the prototype on first use, never at start.
- `=LW.MEASURE(name, names, [as_of])` spills value, unit and Source. The hosted add-in also lists the formula, but the hosted service answers it with "Measures run on this computer only."

Exit criteria
- Tests for spec checks 10, 16 (Excel part) and 19.
- The tool-choice eval's hosted tool list is unchanged, so its result stands.
- `make test`, `make lint` green.
- Commit: `feat(prototype): get_measure in Claude and LW.MEASURE in Excel, local only`.

### P4. Letter reader and confirmations

Files: `erm/letters.py` (new), `erm/prototype_store.py` (new), `erm/semantic.py`, `erm/prototype_tools.py`, `eval/letters.py` (new), `tests/test_letters.py` (new).
- `read_letter` with structured output, `claude-opus-5-5`, AI off by default. Quote check. Proposals stored as `proposed`.
- `confirm_event`. Measure 6 applies confirmed write-downs by the received-date rule.
- `eval/letters.py` scores by the spec's match rule. A stand-in client is used in tests; no call to Anthropic.

Exit criteria
- Tests for spec checks 13, 14 and 20.
- `make test`, `make lint` green.
- Commit: `feat(prototype): letter reader whose events count only once confirmed`.

### P5. Change explainer

Files: `erm/explain.py` (new), `erm/prototype_tools.py`, `tests/test_explain.py` (new).
- Parts by the spec's formulas, a rounding part when needed, and the sum check.
- Template sentence. With AI on, the model returns words with placeholders, and code fills them and rejects anything else.

Exit criteria
- Tests for spec checks 17 and 18, with a stand-in client.
- `make test`, `make lint` green.
- Commit: `feat(prototype): change explainer whose numbers all come from code`.

### P6. Live runs and one more measure

Files: `semantic/measures.yaml`, `erm/semantic.py`, `tests/test_semantic.py`, `erm/explain.py`, `tests/test_explain.py`, `outputs/test-evidence/prototype/` (new).
- With Alexandre's key: `eval/letters.py` on the 20 letters, and 10 explanations. Results, cost and time saved. Expected cost under $1.
- Add a seventh measure, `share_held_via_funds_of_funds`, and time it from a blank entry to a passing test.

Exit criteria
- Spec checks 21 and 22 recorded.
- The seventh measure's time recorded.
- Commit: `test(prototype): live letter and explainer runs, seventh measure`.
- Result, 2026-11-21: letters 27 of 27 found, 0 wrong, $0.13. Explainer run 1 exposed three misleading sentences (wrong main driver, lenders' direction, grammar); fixed in `erm/explain.py` and `tests/test_explain.py`, then run 2 gave 10 of 10 model sentences. Seventh measure: about 18 lines in 2 files, no tool change; wall-clock time not usable. Details in `outputs/test-evidence/prototype/README.md`.

### P7. Verify and open the pull request

Files: none planned. Fixes found here are recorded under this step.
- The verifier agent runs every check in a fresh context.
- `uv run python -m eval.plan_drift plans/embedded-tools-on-semantic-layer.md P<n>` after each step's commit.
- Pull request against `main`. Alexandre merges.

## Risks

| Risk | Step | If it happens |
|---|---|---|
| Fewer than 20 real companies resolve cleanly with loans in both quarters on the public sample | P1 | Take as many as qualify, at least 12, and record the count. The spec's 20 becomes the count found |
| Parquet bytes differ between machines, so the rebuild check fails | P1 | Compare the table's content and a hash of its rows instead of file bytes, and record the change |
| Calling Lender Watch's flag code on synthetic rows needs fields it doesn't have | P2 | Add the field to the generator, never to Lender Watch |
| Lender Watch's engine takes about a minute to load the first time | P2, P3 | Build it once per process, and in tests once per session |
| The model returns placeholders that don't match the part ids | P5 | Rejected by the check, and the template is used. Counted in P6 |
| Templated letters make the reader look better than it is | P6 | Stated with every result, as the spec requires |
