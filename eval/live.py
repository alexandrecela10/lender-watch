"""Live judge check on the answer key: ask the judge again and catch a drop in matching quality.

Spec: specs/ai-drift-tracking.md. Asks only the pairs the chosen method sends to the judge (a wider name hit that
the exact-name rule doesn't settle), through erm.api.call_judge, the product's own call. Fails below the floors in
evals/thresholds.yaml. Stops at a cost or call cap. Prints counts only: no company name reaches the output.
The labels are Claude's, not checked by a person.

Usage:
    uv run python -m eval.live --dry-run
    uv run python -m eval.live [--last LAST.md] [--summary OUT.md] [--repeat 3] [--write-reference PATH]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from erm.match.rules import is_clear_exact
from eval.compare import pair_features, score
from eval.offline import THRESHOLDS, doc_freq_table, load

REFERENCE = "evals/live_reference.csv"
EST_USD_PER_CALL = (
    0.0046  # observed: 24 live calls cost $0.109 on 2026-11-07 (demo list)
)
MARKER = "<!-- live-check "

# A judge takes one pair row and returns (verdict, model, cost_usd or None). It raises on an API error.
Judge = Callable[[object], tuple[str, str, float | None]]


@dataclass
class Result:
    status: str = "PASS"
    calls: int = 0
    errors: int = 0
    cost_usd: float = 0.0
    models: Counter = field(default_factory=Counter)
    verdicts: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    changed: int | None = None
    seconds: int = 0
    stop: str = ""


def pairs_to_ask(d: pd.DataFrame) -> np.ndarray:
    """The pairs method e sends to the judge: a wider name hit the exact-name rule doesn't settle."""
    df, total = doc_freq_table()
    exact = (
        np.array([is_clear_exact(f) for f in pair_features(d, df, total)])
        & d.is_name_hit.values
    )
    return d.is_wide_hit.values & ~exact, exact


def live_judge() -> Judge:
    """The product's call, with filing rows cut to 170 characters as the product does."""
    from erm.api import call_judge, default_client

    client = default_client()

    def ask(r) -> tuple[str, str, float | None]:
        details: dict = {}
        examples = [str(e)[:170] for e in (r.example_1, r.example_2) if e]
        v = call_judge(
            client, r.company_name, r.sector, r.sponsor, r.candidate, examples, details
        )
        return v.verdict, details.get("model", ""), details.get("cost_usd")

    return ask


def run_once(
    d: pd.DataFrame, ask_mask: np.ndarray, exact: np.ndarray, judge: Judge, lim: dict
) -> Result:
    import anthropic

    res, t0 = Result(), time.monotonic()
    for r in d[ask_mask].itertuples():
        if res.cost_usd >= lim["cost_cap_usd"]:
            res.status, res.stop = "INCOMPLETE", "cost cap reached"
            break
        if res.calls >= lim["call_cap"]:
            res.status, res.stop = "INCOMPLETE", "call cap reached"
            break
        res.calls += 1
        try:
            verdict, model, cost = judge(r)
        except anthropic.APIError:
            res.errors += 1
            continue
        res.verdicts[int(r.pair_id)] = verdict
        res.models[model or "unknown"] += 1
        res.cost_usd = round(
            res.cost_usd + (lim["unknown_call_usd"] if cost is None else cost), 6
        )
    res.seconds = int(time.monotonic() - t0)
    if res.status == "INCOMPLETE":
        return res
    if res.errors > lim["max_error_share"] * max(res.calls, 1):
        res.status, res.stop = "ERROR", f"{res.errors} of {res.calls} calls failed"
        return res
    answered = d.pair_id.isin(list(res.verdicts)).values | ~ask_mask
    sub = d[answered]
    live = sub.pair_id.map(res.verdicts).fillna("").values
    pred = exact[answered] | ((live == "match") & sub.is_wide_hit.values)
    res.scores = score(pred, sub)
    return res


def judge_floors(res: Result, floors: dict) -> None:
    if res.status != "PASS":
        return
    s = res.scores
    if (
        s["pair_precision"] < floors["pair_precision"]
        or s["pair_recall"] < floors["pair_recall"]
    ):
        res.status = "FAIL"


def compare_reference(res: Result, path: str | None = None) -> None:
    path = path or REFERENCE
    if not Path(path).exists() or not res.verdicts:
        return
    ref = dict(pd.read_csv(path)[["pair_id", "verdict"]].itertuples(index=False))
    both = [p for p in res.verdicts if p in ref]
    res.changed = sum(res.verdicts[p] != ref[p] for p in both)


def parse_last(text: str) -> dict | None:
    """The machine line in the last history comment: date, status, scores. None if absent."""
    m = re.search(re.escape(MARKER) + r"(\{.*?\}) -->", text or "")
    return json.loads(m.group(1)) if m else None


def summary(
    res: Result, floors: dict, last: dict | None, n_ask: int, today: str
) -> str:
    s = res.scores
    models = ", ".join(f"{m} ({n})" for m, n in res.models.most_common()) or "none"
    lines = [f"live judge check, {today}, model {models}, {res.calls} of {n_ask} calls"]
    if s:
        lines.append(
            f"precision {s['pair_precision']:.3f} (floor {floors['pair_precision']:.2f})   "
            f"recall {s['pair_recall']:.3f} (floor {floors['pair_recall']:.2f})"
        )
        prev = (
            f"last run {last['fp']}"
            if last and last.get("fp") is not None
            else "no last run"
        )
        changed = (
            "no reference yet"
            if res.changed is None
            else f"{res.changed} of {len(res.verdicts)}"
        )
        lines.append(
            f"false matches {s['fp']} ({prev})  verdicts changed since the reference: {changed}"
        )
    lines.append(
        f"errors {res.errors}  cost ${res.cost_usd:.2f}  time {res.seconds // 60}m {res.seconds % 60}s"
    )
    lines.append("labels are Claude's, not checked by a person")
    if s and (
        s["fp"] > 0 or (last and last.get("fp") is not None and s["fp"] > last["fp"])
    ):
        lines.append(f"WARN false matches rose to {s['fp']}")
    lines.append(res.status + (f": {res.stop}" if res.stop else ""))
    machine = {
        "date": today,
        "status": res.status,
        "calls": res.calls,
        "errors": res.errors,
        "cost": res.cost_usd,
    }
    if s:
        machine |= {
            "precision": s["pair_precision"],
            "recall": s["pair_recall"],
            "fp": s["fp"],
        }
    return (
        "```\n" + "\n".join(lines) + "\n```\n" + MARKER + json.dumps(machine) + " -->\n"
    )


def main(argv: list[str] | None = None, judge: Judge | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--last", help="file holding the last history comment")
    ap.add_argument("--summary", help="write the summary (history comment body) here")
    ap.add_argument("--write-reference", help="write the first run's verdicts here")
    ap.add_argument("--thresholds", default=THRESHOLDS)
    a = ap.parse_args(argv)

    cfg = yaml.safe_load(open(a.thresholds))
    floors, lim = cfg, cfg["live"]
    d = load()
    ask_mask, exact = pairs_to_ask(d)
    n_ask = int(ask_mask.sum())

    if a.dry_run:
        ids = d.pair_id[ask_mask].astype(int).tolist()
        print(
            f"{n_ask} pairs to ask, estimated ${n_ask * EST_USD_PER_CALL:.2f}, caps ${lim['cost_cap_usd']}"
        )
        print("pair ids: " + " ".join(map(str, ids)))
        return 0
    if judge is None:
        from dotenv import load_dotenv

        load_dotenv(".env")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("skipped: no ANTHROPIC_API_KEY")
            return 0
        from erm import telemetry

        telemetry.configure()
        judge = live_judge()

    last = (
        parse_last(Path(a.last).read_text())
        if a.last and Path(a.last).exists()
        else None
    )
    today = dt.date.today().isoformat()
    results, worst = [], 0
    for i in range(a.repeat):
        res = run_once(d, ask_mask, exact, judge, lim)
        judge_floors(res, floors)
        compare_reference(res)
        text = summary(res, floors, last, n_ask, today)
        print(text)
        results.append(res)
        worst = max(worst, 0 if res.status == "PASS" else 1)
        if i == 0 and a.write_reference and res.status == "PASS":
            pd.DataFrame(
                sorted(res.verdicts.items()), columns=["pair_id", "verdict"]
            ).to_csv(a.write_reference, index=False)
        if a.summary:
            with open(a.summary, "a") as f:
                f.write(text)
        last = parse_last(text)
    if a.repeat > 1:
        done = [r for r in results if r.scores]
        if done:
            ps = [r.scores["pair_precision"] for r in done]
            rs = [r.scores["pair_recall"] for r in done]
            first = done[0].verdicts
            flips = [
                sum(r.verdicts.get(p) != v for p, v in first.items() if p in r.verdicts)
                for r in done[1:]
            ]
            print(
                f"spread over {len(done)} runs: precision {min(ps):.3f} to {max(ps):.3f}, "
                f"recall {min(rs):.3f} to {max(rs):.3f}, verdicts changed vs run 1: {flips}"
            )
    return worst


if __name__ == "__main__":
    sys.exit(main())
