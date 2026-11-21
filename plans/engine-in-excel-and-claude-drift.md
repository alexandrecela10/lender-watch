# Drift log: engine-in-excel-and-claude.md

One row per build step. A departure is a file the step changed that its plan step does not name, or a planned file it left unchanged.

| Date | Step | Changed, not planned | Planned, not changed |
|---|---|---|---|
| 2026-11-21 | S0 | none | none |
| 2026-11-21 | S1 | `eval/run_full_list.py`, `specs/engine-in-excel-and-claude.md` | `erm/retrieve.py` |
| 2026-11-21 | S2 | `tests/conftest.py` | `erm/cli.py`, `tests/test_api.py` |
| 2026-11-21 | S3 | `.claude/skills/reconcile-companies/SKILL.md`, `erm/lender_tools.py`, `erm/mcp_remote.py`, `tests/test_excel_addin.py` | `.claude/skills/reconcile-companies/`, `README.md`, `erm/connectors/bdc.py` |
| 2026-11-21 | S4 | `erm/telemetry.py` | `app/desk/server.py` |
| 2026-11-21 | S5 | `app/desk/excel/api.js`, `erm/service.py`, `tests/test_names.py` | none |
| 2026-11-21 | S6 | `.gitignore`, `outputs/test-evidence/excel-claude/tool-choice-run1.md`, `outputs/test-evidence/excel-claude/tool-choice-run1.txt`, `outputs/test-evidence/excel-claude/tool-choice-runs2-3.md`, `outputs/test-evidence/excel-claude/tool-choice-runs2-3.txt` | none |
