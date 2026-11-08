"""Check the share of names needing a person's review against its expected range (Stage 6 of the SDLC playbook).

Reads counts from run_metrics (ERM_METRICS_PATH picks the file), compares them with evals/bands.yaml and
reports in plain English. Outside the range it writes a draft intent. No AI model and no outside call is used.

    uv run python -m eval.bands              check the real run records
    uv run python -m eval.bands --simulate   made-up runs in a temporary database, marked SIMULATED

Exit code: 1 when the share is outside the range, otherwise 0.
Only counts and dates are read, so no company name can reach the report or the draft.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from erm.telemetry import METRICS_PATH, write_metrics

BANDS_PATH = Path("evals/bands.yaml")
INTENT_DIR = Path("intent")
EVIDENCE_DIR = Path("outputs/test-evidence/stage6")

SIMULATED_SOURCE = "simulated"
SIMULATED_BANNER = (
    "SIMULATED. These are made-up run records in a temporary database. "
    "No real run or company is involved."
)

NO_RUNS, TOO_FEW, INSIDE, HIGH, LOW = "no_runs", "too_few", "inside", "high", "low"


@dataclass
class Result:
    state: str
    runs: int
    names: int
    needing_review: int
    baseline: float
    low: float | None
    high: float | None
    simulated: bool
    first_run: str | None
    last_run: str | None

    @property
    def breached(self) -> bool:
        return self.state in (HIGH, LOW)

    @property
    def share(self) -> float | None:
        return self.needing_review / self.names if self.names else None


def load_config(path: Path = BANDS_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def recent_runs(db: Path, window: int) -> list[tuple]:
    """Finished judge-on runs that counted names, newest first. Reads no name, id or free text, except an exact check on source."""
    if not db.exists():
        return []
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as con:
        try:
            return con.execute(
                "SELECT names_in, names_needing_review, started_at, source = ? FROM run_metrics"
                " WHERE judge_on = 1 AND status = 'ok' AND names_in > 0"
                " ORDER BY started_at DESC LIMIT ?",
                (SIMULATED_SOURCE, window),
            ).fetchall()
        except sqlite3.OperationalError:  # file exists, no table yet
            return []


def limits(p: float, n: int, deviations: float) -> tuple[float, float]:
    """Expected range for a yes/no share p over n names."""
    spread = deviations * math.sqrt(p * (1 - p) / n)
    return max(0.0, p - spread), min(1.0, p + spread)


def check(db: Path, cfg: dict) -> Result:
    b = cfg["baseline"]
    p = b["names_needing_review"] / b["names"]
    rows = recent_runs(db, cfg["window_runs"])
    names = sum(r[0] for r in rows)
    needing = sum(r[1] for r in rows)
    low = high = None
    if not rows:
        state = NO_RUNS
    elif names < cfg["min_names"]:
        state = TOO_FEW
    else:
        low, high = limits(p, names, cfg["deviations"])
        share = needing / names
        state = HIGH if share > high else LOW if share < low else INSIDE
    return Result(
        state,
        len(rows),
        names,
        needing,
        p,
        low,
        high,
        simulated=any(r[3] for r in rows),
        first_run=rows[-1][2][:10] if rows else None,
        last_run=rows[0][2][:10] if rows else None,
    )


def pct(x: float) -> str:
    return f"{x:.0%}"


def one_in(x: float) -> str:
    return f"about 1 name in {round(1 / x)}" if x > 0 else "no names"


def _measured(r: Result) -> str:
    return (
        f"- Measured: {pct(r.share)} of names needed a person's review "
        f"({r.needing_review} of {r.names} names, {one_in(r.share)}), across the latest {r.runs} runs with the AI judge on."
    )


def _caveat(cfg: dict) -> str:
    b = cfg["baseline"]
    return (
        f"- Limit of this check: the expected level comes from one full run on {b['observed_on']} "
        f"({b['names_needing_review']} of {b['names']} names), not from history. Treat the range as provisional."
    )


def _meaning(r: Result) -> str:
    if r.state == HIGH:
        return "Analysts have more names to check by hand than expected."
    return "Fewer names reach a person than expected. The AI judge may be deciding cases it used to leave to a person."


def report(r: Result, cfg: dict, draft: Path | None = None) -> str:
    lines = [SIMULATED_BANNER, ""] if r.simulated else []
    if r.state == NO_RUNS:
        lines += [
            "No check made: there are no finished runs with the AI judge on yet.",
            "- Runs appear here after the app, the command line or the agent tools process names with the judge on.",
            _caveat(cfg),
        ]
    elif r.state == TOO_FEW:
        lines += [
            f"No check made: only {r.names} names so far, and at least {cfg['min_names']} are needed.",
            "- A few names swing the share too much to mean anything.",
            _measured(r),
            _caveat(cfg),
        ]
    else:
        head = {
            INSIDE: "No action needed: the share of names needing a person is inside the expected range.",
            HIGH: "Action needed: too many names need a person's review. Read the draft intent and decide whether to fix, schedule or dismiss.",
            LOW: "Action needed: too few names reach a person's review. Read the draft intent and decide whether to fix, schedule or dismiss.",
        }[r.state]
        lines += [
            head,
            _measured(r),
            f"- Expected range: {pct(r.low)} to {pct(r.high)} for this many names. A share outside it is unlikely to be chance alone.",
            f"- Expected level: {pct(r.baseline)}.",
            _caveat(cfg),
        ]
        if r.breached:
            lines.append(f"- What it means: {_meaning(r)}")
        if draft:
            lines.append(f"- Draft intent, for a person to review: {draft}")
    return "\n".join(lines) + "\n"


def draft_intent(r: Result, cfg: dict) -> str:
    """Draft in the format of .claude/skills/intent-md/SKILL.md. Its numbers come only from the run records and the config."""
    b = cfg["baseline"]
    word = "more" if r.state == HIGH else "fewer"
    sim = "SIMULATED: " if r.simulated else ""
    harm = (
        "Each extra name is a match an analyst confirms by hand, so a list takes longer to get through."
        if r.state == HIGH
        else "If the AI judge is deciding cases it used to leave to a person, a wrong loan could reach an analyst unchecked."
    )
    return f"""# {sim}Intent: {word} names than expected need a person's review

{SIMULATED_BANNER + chr(10) + chr(10) if r.simulated else ""}Author: `eval/bands.py`, a script. No AI model wrote this. Status: draft, for a person to correct or dismiss before anything is built.
Source: run records from {r.first_run} to {r.last_run}, compared with the provisional range in `evals/bands.yaml`.
Evidence: {"made-up run records." if r.simulated else "counts from our own run records."} No LP analyst has been interviewed. The pain is inferred from public signals.

## Problem

- Who has it: LP analysts who confirm unclear company matches before they rely on a lender's loan value.
- What went wrong: {pct(r.share)} of names needed a person's review, and the expected range for this many names is {pct(r.low)} to {pct(r.high)}.
- Why it matters: {harm}
- The case: {r.needing_review} of {r.names} names across the latest {r.runs} runs with the AI judge on{" (made up)" if r.simulated else ""}, from our run records.
- The cause is unobserved. The records hold counts only, so a person must look at what changed.

## Proposed outcome

A person learns why the share moved, then decides to fix, schedule or dismiss.

What should change:
- Share of names needing a person's review: today {pct(r.share)}, target back inside {pct(r.low)} to {pct(r.high)}, or a corrected range if this level is the new normal.
- Time from this finding to a decision: unobserved.

What must not get worse:
- Wrong loans shown to an analyst. Precision on the answer key stays at or above the {load_floor():.2f} floor.
- Values shown without a filing link: 0.

## Affected users and systems

Users: LP analysts on a private equity funds team.
Systems: matching in `erm/`, saved decisions, the optional AI judge, the run records.

## Constraints

- Public data only. Never name an organisation Alexandre is applying to.
- Every fact keeps its source.
- Run records hold counts only. Diagnosis must not add company names to them.
- The AI judge stays off by default.
- The expected range is provisional: one run on {b["observed_on"]}, {b["names_needing_review"]} of {b["names"]} names.

## Open questions

- Did the judge's model or instructions change between these runs? If yes, re-run the live check first.
- Were different kinds of lists run? If yes, the range may be wrong rather than the product.
- Did saved answers from people lower the share? If yes, a list run twice is not a fair comparison.
- Is the range right? Decide after a quarter of real runs. If this finding is dismissed, record why and adjust the range.
"""


def load_floor() -> float:
    return yaml.safe_load(Path("evals/thresholds.yaml").read_text())["pair_precision"]


def draft_name(r: Result) -> str:
    stem = f"names-needing-review-{r.state}"
    return (
        f"SIMULATED-{stem}.md"
        if r.simulated
        else f"{stem}-{dt.date.today().isoformat()}.md"
    )


def write_draft(r: Result, cfg: dict, out_dir: Path) -> Path:
    if r.simulated and out_dir.resolve() == INTENT_DIR.resolve():
        raise SystemExit("Refused: a SIMULATED draft never goes in intent/.")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / draft_name(r)
    path.write_text(draft_intent(r, cfg))
    return path


def open_pull_request(draft: Path, r: Result, run=subprocess.run) -> None:
    """Off unless --open-pr is passed. Puts the draft on its own branch and opens a draft pull request for review."""
    if r.simulated:
        raise SystemExit("Refused: a SIMULATED draft never becomes a pull request.")
    branch = f"intent/{draft.stem}"
    for cmd in (
        ["git", "switch", "-c", branch],
        ["git", "add", str(draft)],
        ["git", "commit", "-m", f"docs(intent): draft from range check, {draft.stem}"],
        ["git", "push", "-u", "origin", branch],
        ["gh", "pr", "create", "--draft", "--fill"],
        ["git", "switch", "-"],
    ):
        run(cmd, check=True)


def simulated_rows() -> list[dict]:
    """Twenty made-up runs of 15 names, 4 of them needing review (27%): far above the provisional range."""
    return [
        {
            "request_id": f"simulated-{i:02d}",
            "session_id": "simulated",
            "source": SIMULATED_SOURCE,
            "started_at": f"2000-01-{i + 1:02d}T00:00:00Z",
            "judge_on": 1,
            "status": "ok",
            "names_in": 15,
            "names_matched": 8,
            "names_needing_review": 4,
            "flagged": 0,
            "worth_a_look": 0,
            "duration_ms": 1000,
            "judge_calls": 0,
            "judge_cost_usd": 0.0,
        }
        for i in range(20)
    ]


def run(
    db: Path, cfg: dict, out_dir: Path, open_pr: bool = False
) -> tuple[Result, str]:
    r = check(db, cfg)
    draft = write_draft(r, cfg, out_dir) if r.breached else None
    text = report(r, cfg, draft)
    if draft and open_pr:
        open_pull_request(draft, r)
    return r, text


def simulate(cfg: dict, out_dir: Path) -> tuple[Result, str]:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "simulated.sqlite"
        for row in simulated_rows():
            write_metrics(db, row)
        return run(db, cfg, out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--simulate",
        action="store_true",
        help="use made-up runs in a temporary database; the real records are never opened",
    )
    ap.add_argument(
        "--draft-dir",
        type=Path,
        help="where a draft intent goes (default: intent/, or the evidence folder with --simulate)",
    )
    ap.add_argument(
        "--open-pr",
        action="store_true",
        default=False,
        help="off by default: also open a draft pull request from a real draft (pushes to GitHub)",
    )
    a = ap.parse_args()
    cfg = load_config()
    if a.simulate:
        if a.open_pr:
            raise SystemExit("Refused: a SIMULATED draft never becomes a pull request.")
        r, text = simulate(cfg, a.draft_dir or EVIDENCE_DIR)
    else:
        db = Path(os.environ.get("ERM_METRICS_PATH", METRICS_PATH))
        r, text = run(db, cfg, a.draft_dir or INTENT_DIR, a.open_pr)
    print(text, end="")
    sys.exit(1 if r.breached else 0)


if __name__ == "__main__":
    main()
