"""Letter reader eval: how many of the generator's events does the reader find, and how many does it invent?

Spec: specs/embedded-tools-on-semantic-layer.md, section 4. The truth is data/synthetic/events.csv, written by the
generator, not a model's labels. The letters are built by code from templates, so they are easier than real letters:
every result says so. Calls Anthropic only with --live. Prints counts only, never letter text.

Usage:
    uv run python -m eval.letters --live [--summary OUT.md]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from erm import letters
from erm.match.judge import cost_usd
from erm.semantic import SYN, Portfolio

SIZE_TOLERANCE = 0.5
FIELDS = ("company_id", "type", "effective", "size_pct_cost")


def truth() -> pd.DataFrame:
    return pd.read_csv(SYN / "events.csv", keep_default_na=False, dtype={"letter": str})


def _size(x):
    return None if x in ("", None) else float(x)


def matches(p: dict, t) -> bool:
    """Found: same company and type, exact effective date, and for a write-down a size within 0.5 points."""
    if (
        p.get("company_id") != t.company_id
        or p["type"] != t.type
        or p["effective"] != t.effective
    ):
        return False
    if t.type == "write_down":
        return (
            p.get("size_pct_cost") is not None
            and abs(p["size_pct_cost"] - _size(t.size_pct_cost)) <= SIZE_TOLERANCE
        )
    return True


def score(proposals: dict[str, list[dict]], events: pd.DataFrame) -> dict:
    """proposals: letter number -> proposed events (with company_id). One proposal matches at most one event."""
    found = wrong = 0
    field_right = dict.fromkeys(FIELDS, 0)
    for letter, group in events.groupby("letter"):
        pending = list(proposals.get(letter, []))
        for t in group.itertuples():
            hit = next((p for p in pending if matches(p, t)), None)
            if hit is None:
                # Partly right proposals still teach which field the reader gets wrong.
                near = next(
                    (p for p in pending if p.get("company_id") == t.company_id), None
                )
                if near is not None:
                    for f in FIELDS:
                        field_right[f] += _field_ok(near, t, f)
                continue
            found += 1
            pending.remove(hit)
            for f in FIELDS:
                field_right[f] += 1
        wrong += len(pending)
    total = len(events)
    return {
        "events": total,
        "found": found,
        "wrong": wrong,
        "fields_right": field_right,
    }


def _field_ok(p: dict, t, f: str) -> bool:
    if f == "size_pct_cost":
        if t.type != "write_down":
            return p.get("size_pct_cost") is None
        return (
            p.get("size_pct_cost") is not None
            and abs(p["size_pct_cost"] - _size(t.size_pct_cost)) <= SIZE_TOLERANCE
        )
    return p.get(f) == getattr(t, f)


def run(client) -> tuple[dict, float, int]:
    portfolio = Portfolio()
    events = truth()
    proposals, cost, start = {}, 0.0, time.monotonic()
    for path in sorted((SYN / "letters").glob("*.md")):
        out = letters.read_letter(path.read_text(), client)
        c = cost_usd(out["model"], out["usage"])
        cost += 0.05 if c is None else c
        kept = []
        for e in out["kept"]:
            found = portfolio.find(e["company"])
            kept.append(
                {**e, "company_id": found.company_id if found is not None else None}
            )
        proposals[path.stem] = kept
    return score(proposals, events), cost, round(time.monotonic() - start)


def summary(s: dict, cost: float, seconds: int) -> str:
    lines = [
        "## Letter reader (templated synthetic letters, easier than real ones)",
        "",
        f"Model `{letters.MODEL}`, 20 letters, {seconds} s, ${cost:.2f}. Truth from the generator, not a model.",
        "",
        f"- Events found: {s['found']} of {s['events']}",
        f"- Proposals that match no event: {s['wrong']}",
        "- Fields right on events found or nearly found: "
        + ", ".join(f"{f} {n} of {s['events']}" for f, n in s["fields_right"].items()),
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    a = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    a.add_argument("--live", action="store_true", required=True)
    a.add_argument("--summary")
    args = a.parse_args(argv)
    from erm.api import default_client

    client = default_client()
    if client is None:
        print("No ANTHROPIC_API_KEY: skipped. Nothing was sent.")
        return 0
    s, cost, seconds = run(client)
    text = summary(s, cost, seconds)
    print(text)
    if args.summary:
        Path(args.summary).write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
