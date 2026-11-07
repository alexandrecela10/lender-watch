"""Track where a build departs from its plan.

Compares the files a build step changed with the files its plan step names
(the "Files:" line under "### <step>."), and appends one row per run to
plans/<plan>-drift.md.

Usage, from the repo root, right after committing a one-commit step:
    uv run python -m eval.plan_drift plans/instrumentation.md I1
Then amend the commit with the log. For a longer step, pass --base <commit before it>.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path

HEADER = (
    "# Drift log: {plan}\n\n"
    "One row per build step. A departure is a file the step changed that its plan step does not name, "
    "or a planned file it left unchanged.\n\n"
    "| Date | Step | Changed, not planned | Planned, not changed |\n"
    "|---|---|---|---|\n"
)


def planned_files(plan_text: str, step: str) -> set[str]:
    """Paths in backticks on the 'Files:' line of '### <step>.'."""
    section = re.search(
        rf"^### {re.escape(step)}\..*?(?=^### |^## |\Z)", plan_text, re.S | re.M
    )
    if not section:
        raise SystemExit(f"step {step} not found in plan")
    line = re.search(r"^Files:(.*)$", section.group(0), re.M)
    if not line:
        raise SystemExit(f"step {step} has no 'Files:' line")
    return set(re.findall(r"`([^`]+)`", line.group(1)))


def departures(
    planned: set[str], changed: set[str], ignore: set[str]
) -> tuple[list[str], list[str]]:
    changed = changed - ignore
    return sorted(changed - planned), sorted(planned - changed)


def changed_files(base: str) -> set[str]:
    def git(*args: str) -> set[str]:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout
        return {p for p in out.splitlines() if p}

    # Run after committing the step (--base <commit before it>), so files nobody
    # committed, such as a local editor config, never count as drift.
    return git("diff", "--name-only", base, "HEAD")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plan")
    ap.add_argument("step")
    ap.add_argument("--base", default="HEAD~1")
    a = ap.parse_args()

    plan = Path(a.plan)
    log = plan.with_name(f"{plan.stem}-drift.md")
    extra, missing = departures(
        planned_files(plan.read_text(), a.step),
        changed_files(a.base),
        ignore={str(plan), str(log)},
    )
    row = (
        f"| {dt.date.today()} | {a.step} | {', '.join(f'`{p}`' for p in extra) or 'none'} "
        f"| {', '.join(f'`{p}`' for p in missing) or 'none'} |\n"
    )
    if not log.exists():
        log.write_text(HEADER.format(plan=plan.name))
    with log.open("a") as f:
        f.write(row)
    print(row, end="")


if __name__ == "__main__":
    main()
