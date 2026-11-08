# Decision: the drift log is the control for plan drift

**Date:** 2026-11-08. **Status:** proposed, for Alexandre to accept in the pull request. **Chosen by:** Claude, as a default.

**Decision:** keep the drift log as the control, and say so in `CLAUDE.md`. No hook blocks a commit.

**Why:** the rule in `CLAUDE.md` and what enforces it must agree, and today they don't say the same thing. Alexandre's instruction on the rule was to flag a departure, not always to act on it.

**Example:** step D3 changed `README.md`, which its plan didn't list. The log flagged it and the reviewer saw it. With a blocking hook, that commit would have stopped until the plan was edited, for a harmless file.

**Not chosen:** a hook that blocks a commit when the log shows unplanned files and the plan wasn't touched. It matches the playbook's "update the plan in the same commit" (page 20). It costs an edit for every harmless departure.

**What this does not fix (from the PO review):**
- Nothing runs the log tool automatically, so a step can skip it.
- The tool can't process a step with no file list, such as D4.

**Revisit if:** a departure that mattered reaches `main` without a log row.
