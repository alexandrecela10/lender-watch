"""Offline eval gate: replay stored judge verdicts and the exact-name rule against the answer key.

Scores method `e_exact_name_rule_then_judge` from eval/compare.py at pair level and exits 1 when precision or
recall falls below evals/thresholds.yaml. No network, no API key, no judge calls: verdicts come from
data/eval/judge_results.csv.

Usage: uv run python -m eval.offline [--answer-key PATH] [--thresholds PATH]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
import yaml

from erm.match.rules import is_clear_exact
from eval.compare import pair_features, score

ANSWER_KEY = "data/eval/answer_key.csv"
JUDGE = "data/eval/judge_results.csv"
# Pool rows with the name-search flags (is_name_hit, is_wide_hit) that compare.load computed. They depend only on
# the pool text, so reading them here skips about two minutes of search; labels and verdicts are joined fresh.
POOL = "data/eval/scored_pairs.csv"
THRESHOLDS = "evals/thresholds.yaml"
# Committed copy of the holdings. Its 30 June 2026 texts are the same set compare.py reads from the
# git-ignored data/holdings_clean.parquet, so word rarity, and with it the exact-name rule, comes out the same.
HOLDINGS = "data/public/holdings.parquet"


def doc_freq_table(path: str = HOLDINGS) -> tuple[dict[str, int], int]:
    """Same as compare.doc_freq_table, read from a committed file."""
    from erm.textparse import norm

    h = pd.read_parquet(path, columns=["period", "raw_text"])
    q = h[h.period == "2026-06-30"].raw_text.drop_duplicates()
    df: dict[str, int] = {}
    for t in q:
        for w in set(norm(t).split()):
            df[w] = df.get(w, 0) + 1
    return df, len(q)


def load(answer_key: str = ANSWER_KEY) -> pd.DataFrame:
    """Pool rows joined to the answer key labels and the stored judge verdicts, as compare.load does."""
    pool = (
        pd.read_csv(POOL).fillna("").drop(columns=["label", "verdict", "link_margin"])
    )
    key = pd.read_csv(answer_key)[["pair_id", "label"]]
    judge = pd.read_csv(JUDGE)[["pair_id", "verdict"]]
    return pool.merge(key, on="pair_id").merge(judge, on="pair_id", how="left")


def predict(d: pd.DataFrame) -> np.ndarray:
    """Method e from compare.main: exact-name rule, else judge says match on a wider name hit."""
    df, total = doc_freq_table()
    feats = pair_features(d, df, total)
    hit = d.is_name_hit.values
    exact = np.array([is_clear_exact(f) for f in feats]) & hit
    verdict_match = (d.verdict == "match").values
    return exact | (verdict_match & d.is_wide_hit.values)


def run(answer_key: str = ANSWER_KEY, thresholds: str = THRESHOLDS) -> int:
    limits = yaml.safe_load(open(thresholds))
    d = load(answer_key)
    r = score(predict(d), d)

    p, rc = r["pair_precision"], r["pair_recall"]
    ok = p >= limits["pair_precision"] and rc >= limits["pair_recall"]
    print(f"method      {limits['method']}")
    print(f"answer key  {answer_key} ({len(d)} pairs, unsure left out)")
    print(f"precision   {p:.3f}  threshold {limits['pair_precision']:.2f}")
    print(f"recall      {rc:.3f}  threshold {limits['pair_recall']:.2f}")
    print(f"tp {r['tp']}  fp {r['fp']}  fn {r['fn']}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--answer-key", default=ANSWER_KEY)
    ap.add_argument("--thresholds", default=THRESHOLDS)
    a = ap.parse_args()
    sys.exit(run(a.answer_key, a.thresholds))


if __name__ == "__main__":
    main()
