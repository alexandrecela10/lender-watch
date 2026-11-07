# Drift log: ai-drift-tracking.md

One row per build step. A departure is a file the step changed that its plan step does not name, or a planned file it left unchanged.

| Date | Step | Changed, not planned | Planned, not changed |
|---|---|---|---|
| 2026-11-07 | D1 | `.claude/agents/verifier.md`, `CLAUDE.md` | none |
| 2026-11-07 | D2 | `.claude/agents/verifier.md`, `CLAUDE.md` | none |
| 2026-11-07 | D3 | `.claude/agents/verifier.md`, `CLAUDE.md`, `eval/live.py`, `tests/test_live_eval.py` | `.claude/skills/data-handling/SKILL.md` |

Notes:
- Every step changed `CLAUDE.md` and the verifier, only to update the healthy test count.
- D3: `eval/live.py` now reads the last result in a comment, not the first, and has a test for it.
- D3: the data-handling skill line landed in this plan pull request (#5) instead.
| 2026-11-07 | D4 | none | none |

D4 ran on this machine with the `.env` key instead of on `main`, because merges wait for Alexandre. Same code, same 145 pairs. Three runs: precision 1.000 and recall 0.936 each time, 0 false matches, 1 of 145 verdicts changed once, $1.97 in total.
