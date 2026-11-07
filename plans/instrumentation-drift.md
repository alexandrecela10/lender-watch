# Drift log: instrumentation.md

One row per build step. A departure is a file the step changed that its plan step does not name, or a planned file it left unchanged.

| Date | Step | Changed, not planned | Planned, not changed |
|---|---|---|---|
| 2026-11-07 | I1 | `.claude/agents/verifier.md`, `CLAUDE.md`, `eval/plan_drift.py` | none |
| 2026-11-07 | I2 | `.claude/agents/verifier.md`, `CLAUDE.md`, `erm/telemetry.py` | none |
