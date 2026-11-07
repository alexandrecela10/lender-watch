---
name: intent-md
description: Writes an intent file in intent/ for this repo. Use when someone asks to write an intent, capture a new idea, a new use case or a new problem to solve, turn an opportunity analysis (/pm-os:opportunity-analysis or outputs/opportunity-analyses/) into an intent, or asks what an intent for a new feature would contain.
---

# Intent file

1. Pick a short kebab-case slug for the use case. The file is `intent/<slug>.md`. Use `intent/lp-credit-readthrough.md` as the model for length and tone.
2. Look for a matching opportunity analysis in `outputs/opportunity-analyses/`. If one exists, pull the problem, the pain example, the numbers and the open questions from it, and name it on a `Source:` line.
3. Start with a header: author, status (draft), source, and an evidence line saying what the pain is based on. Until real users are interviewed, say the pain is inferred from public signals.
4. Write these sections, in this order:
   - **Problem**: 3 to 5 short bullets: who has it, what goes wrong, why it matters, and one concrete case with a number and its source. No file paths, function names or code; that proof goes in the spec.
   - **Proposed outcome**: what the user puts in and gets back. Then "What should change" with metric, baseline and target, and "What must not get worse".
   - **Affected users and systems**: users now and later; data sources and repo modules touched.
   - **Constraints**: the hard rules from `CLAUDE.md` that apply, plus any new ones.
   - **Open questions**: what we don't know, and what answer would change the decision.
5. Never invent a number. If a baseline or target isn't observed, name the metric and its direction and write "unobserved".
6. Write in plain English for a reader who doesn't know the code: bullets, short factual sentences, no em dashes, no sales words. Never name an organisation Alexandre is applying to. Company names from public sources are fine.
7. Tell the PM the file path and list every value marked unobserved.
