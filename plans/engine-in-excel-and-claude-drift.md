# Drift log: engine-in-excel-and-claude.md

One row per build step. A departure is a file the step changed that its plan step does not name, or a planned file it left unchanged.

| Date | Step | Changed, not planned | Planned, not changed |
|---|---|---|---|
| 2026-11-21 | S0 | none | none |
| 2026-11-21 | S1 | `eval/run_full_list.py`, `specs/engine-in-excel-and-claude.md` | `erm/retrieve.py` |
| 2026-11-21 | S2 | `tests/conftest.py` | `erm/cli.py`, `tests/test_api.py` |
