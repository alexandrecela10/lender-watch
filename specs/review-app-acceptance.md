# Review app: what the analyst must see

The verifier's browser step (`.claude/agents/verifier.md`, step 6) compares screenshots of the running app against these lines.
Each line is met or not met. A line is met if any screenshot shows it. The app runs in public mode (`ERM_PUBLIC=1`) with the demo list from `data/demo/sample_list.csv` typed in.
Public mode makes no AI calls, so no company name leaves the computer. The local-mode judge checkbox is checked by `tests/test_app.py`.

## Screen 1: before I check anything

- A1. I see the title "Lender Watch" and a line saying values are each lender's own estimate, not investment advice.
- A2. I see "Step 1: Pick a list" with a box where I can type company names, one per line.
- A3. I see no option to send names to an AI.

## Screen 2: after I click "Check lender filings"

- A4. I see "Step 2: Read the result" and a headline saying how many of my 6 companies are flagged.
- A5. KnowBe4 is marked "Flagged" in the results table.
- A6. Not A Real Company Xyzzy shows "No public lender found".
- A7. Below the results table, I see a button labelled "Download as Excel, with a filing link for every loan". (What is inside the file is checked by the verifier's step 5, not here.)

## Screen 3: the proof for one company

- A8. Under "Step 3: Check the proof", I see one row per loan, each with a "Filing" column showing an "Open" link.
- A9. I see the name lenders use for this borrower (for KnowBe4: "KnowBe4 Inc." or "KnowBe4, Inc.").

## Screen 4: the "Matches to confirm" tab

- A10. I see either the matches waiting for my answer, or "Nothing left to confirm on this list."

## Every screen

- A11. I see no error message, red box or Python traceback.
