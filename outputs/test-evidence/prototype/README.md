# Prototype live runs, 2026-11-21

Synthetic data and templated letters. Results show the plumbing works, not how the tools would do on real letters or real holdings.

| Check | Result | Evidence |
|---|---|---|
| 21. Letter reader on 20 letters | 27 of 27 events found, 0 wrong, every field right. 48 s, $0.13 | `letters-run1.md` |
| 22. Ten explanations, model writing the words | Run 1: 9 of 10 from the model, 1 template. Reading them found three flaws, fixed before run 2. Run 2: 10 of 10 from the model, every number from code. Cost not recorded; about 20 calls in total | `explanations-run1-before-fixes.md`, `explanations-run2.md` |
| Seventh measure | `share_via_funds_of_funds`: one 9-line definition, one 5-line function, and a 4-line option on the cost function. No tool, route or Excel change: the tool description lists it from the file. Wall-clock time not usable: a stuck test run inflated it | `semantic/measures.yaml`, `erm/semantic.py` |

## Flaws found in run 1 of the explainer

The number check passed, yet the sentences misled. Each one is fixed in `erm/explain.py`:

1. **Wrong "main driver".** "Driven mainly by KnowBe4", when the biggest part was Cloud Software Group at $19.5m. The model sees no amounts, so it couldn't know. Now it gets the three largest parts only, largest first.
2. **Misleading direction.** The lenders' part read "rose" when lenders had cut their value; "rose" was its effect on the gap. Now the label says what lenders did ("lenders cut their value of the debt"), and the direction says what it did to the gap ("widened the gap").
3. **Grammar.** "Values moved fell". Now the prompt says the direction placeholder is itself the verb.

**Left as is:** one sentence in run 2 reads "widened the gap it by 4.1 points". A grammar slip, with every number still right.
