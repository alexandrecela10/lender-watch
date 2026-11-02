"""Compare matching approaches on the answer key.

Baseline and judge have nothing to tune, so they are scored on all sampled companies. The scoring model and the rule that
auto-accepts pairs are tuned on some companies and scored on the others (company-level cross-validation), because errors
cluster by name and one split can pass or fail by luck.

Levels:
  pair  = one company x one distinct borrower string
  loan  = pairs weighted by holding rows (the PRD's loan-level precision)

Usage: PYTHONPATH=. uv run python eval/compare.py
"""

from __future__ import annotations

import json
import random

import numpy as np
import pandas as pd

from erm.match.features import compute
from erm.match.linkage import LinkageModel
from erm.retrieve import compact_hit, name_variants
from erm.textparse import core, find_mention, name_pattern, norm

TARGET_PRECISION = 0.97
SEED, FOLDS = 17, 5


def wilson(k: float, n: float, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(float((c - r) / d), 3), round(float((c + r) / d), 3)]


def load() -> pd.DataFrame:
    p = pd.read_csv("data/eval_pool.csv").fillna("")
    key = pd.read_csv("data/eval/answer_key.csv")
    d = p.merge(key[["pair_id", "label"]], on="pair_id")
    d = d.merge(pd.read_csv("data/eval/judge_results.csv")[["pair_id", "verdict"]], on="pair_id", how="left")
    text = [" ".join([r.candidate, r.example_1, r.example_2]) for r in d.itertuples()]
    d["is_name_hit"] = [bool(name_pattern(core(n)).search(t)) for n, t in zip(d.company_name, text)]
    d["is_wide_hit"] = [
        any(name_pattern(v).search(t) for v in name_variants(n)) or compact_hit(n, r)
        for n, t, r in zip(d.company_name, text, d.candidate)
    ]
    return d


def doc_freq_table() -> tuple[dict[str, int], int]:
    h = pd.read_parquet("data/holdings_clean.parquet", columns=["period", "raw_text"])
    q = h[h.period == "2026-06-30"].raw_text.drop_duplicates()
    df: dict[str, int] = {}
    for t in q:
        for w in set(norm(t).split()):
            df[w] = df.get(w, 0) + 1
    return df, len(q)


def pair_features(d: pd.DataFrame, df, total):
    out = []
    for r in d.itertuples():
        left, right, trade = (), None, False
        pat = name_pattern(core(r.company_name))
        for text in (r.example_1, r.example_2):
            m = find_mention(text, pat) if text else None
            if m:
                left, right, trade = m.left, m.right, m.trade_name
                break
        out.append(compute(r.company_name, r.candidate, df, total, left, right, trade))
    return out


def score(pred, d: pd.DataFrame) -> dict:
    """Pairs labelled unsure are left out of precision and recall."""
    pred = np.asarray(pred, dtype=bool)
    k = (d.label != "unsure").values
    y, p, w = (d.label.values[k] == "match"), pred[k], d.n_rows.values[k]
    tp, fp, fn = (y & p).sum(), (~y & p).sum(), (y & ~p).sum()
    tpw, fpw, fnw = w[y & p].sum(), w[~y & p].sum(), w[y & ~p].sum()
    truth = set(d.company_id.values[k][y])
    found = set(d.company_id.values[k][y & p])
    wrong_co = set(d.company_id.values[k][~y & p])
    return {
        "pair_precision": round(tp / max(tp + fp, 1), 3),
        "pair_precision_95ci": wilson(tp, tp + fp),
        "pair_recall": round(tp / max(tp + fn, 1), 3),
        "loan_precision": round(tpw / max(tpw + fpw, 1), 3),
        "loan_recall": round(tpw / max(tpw + fnw, 1), 3),
        "tp": int(tp), "fp": int(fp), "fn": int(fn),
        "companies_found": f"{len(found & truth)} of {len(truth)}",
        "companies_with_a_wrong_pair": len(wrong_co),
    }


def tune_accept(s: np.ndarray, y: np.ndarray) -> float:
    """Lowest score whose accepted pairs reach the target precision, with at least 10 accepted."""
    for t in np.arange(-12, 25, 0.5):
        p = s >= t
        if p.sum() >= 10 and y[p].mean() >= TARGET_PRECISION:
            return float(t)
    return 99.0


def main() -> None:
    d = load()
    df, total = doc_freq_table()
    feats = pair_features(d, df, total)
    lab = (d.label != "unsure").values
    hit = d.is_name_hit.values

    # Cross-validated scoring model, trained on the real decision: pairs where the name appears.
    companies = sorted(d.company_id.unique())
    random.Random(SEED).shuffle(companies)
    fold = {c: i % FOLDS for i, c in enumerate(companies)}
    s = np.full(len(d), -99.0)
    accepts = []
    for k in range(FOLDS):
        test = d.company_id.map(fold).values == k
        tr = ~test & lab & hit
        f_tr = [f for f, a in zip(feats, tr) if a]
        y_tr = (d.label.values[tr] == "match")
        model = LinkageModel.fit(f_tr, list(y_tr))
        accept = tune_accept(np.array([model.score(f) for f in f_tr]), y_tr)
        accepts.append(accept)
        for i in np.where(test & hit)[0]:
            s[i] = model.score(feats[i]) - accept  # above 0 means accepted under this fold's bar
    d["link_margin"] = s

    verdict_match = (d.verdict == "match").values
    verdict_unsure = (d.verdict == "unsure").values
    no_left = np.array([f.left_words for f in feats]) == 0
    exact = np.array([f.exact_core and f.distinctiveness >= 0.75 and not f.short_name for f in feats]) & hit & no_left

    approaches = {
        "a_name_hit_baseline": hit,
        "b_scoring_model": s >= 0,
        "c_judge_on_name_hits": verdict_match & hit,
        "c_judge_on_wider_name_hits": verdict_match & d.is_wide_hit.values,
        "c_judge_on_all_search_results": verdict_match,
        "d_scoring_model_then_judge": (s >= 0) | (verdict_match & hit),
        "e_exact_name_rule_then_judge": exact | (verdict_match & d.is_wide_hit.values),
    }
    results = {k: score(v, d) for k, v in approaches.items()}

    n = d.company_id.nunique()

    def review(mask):
        names = d[mask].company_id.nunique()
        return {"names": int(names), "share_of_names": round(names / n, 3), "pairs": int(mask.sum())}

    load_review = {
        "judge_on_name_hits": review(verdict_unsure & hit),
        "judge_on_wider_name_hits": review(verdict_unsure & d.is_wide_hit.values),
        "judge_on_all_search_results": review(verdict_unsure),
    }

    cost = json.load(open("data/eval/judge_cost.json"))
    per_pair = cost["usd"] / cost["pairs"]
    judged = {
        "judge_on_name_hits": int(hit.sum()),
        "judge_on_wider_name_hits": int(d.is_wide_hit.sum()),
        "judge_on_all_search_results": len(d),
        "exact_name_rule_then_judge": int((d.is_wide_hit.values & ~exact).sum()),
    }
    cost_per_100 = {k: round(v / n * 100 * per_pair, 2) for k, v in judged.items()}

    rule_fp = d[exact & (d.label == "no_match").values][["company_name", "candidate"]]
    report = {
        "answer_key": {"companies": n, "pairs": len(d), "match": int((d.label == "match").sum()),
                       "no_match": int((d.label == "no_match").sum()), "unsure": int((d.label == "unsure").sum())},
        "results": results,
        "pairs_needing_person": load_review,
        "batch_usd_per_100_listed_names": cost_per_100,
        "scoring_model_accept_bar_by_fold": accepts,
        "exact_name_rule": {"pairs": int(exact.sum()), "wrong": len(rule_fp)},
        "judge_cost_total": cost,
    }
    json.dump(report, open("data/eval/compare_report.json", "w"), indent=1, default=float)
    d.to_csv("data/eval/scored_pairs.csv", index=False)
    for k, v in results.items():
        print(f"{k:32s} loan P {v['loan_precision']:.3f} R {v['loan_recall']:.3f} | pair P {v['pair_precision']:.3f} {v['pair_precision_95ci']} R {v['pair_recall']:.3f} | fp {v['fp']} fn {v['fn']} | co {v['companies_found']}, wrong {v['companies_with_a_wrong_pair']}")
    print(json.dumps({k: report[k] for k in ["answer_key", "pairs_needing_person", "batch_usd_per_100_listed_names", "scoring_model_accept_bar_by_fold", "exact_name_rule"]}, default=float))
    print(rule_fp.to_string(index=False))
    miss = d[(d.label == "match").values & ~(verdict_match & d.is_wide_hit.values)][["company_name", "candidate", "verdict", "is_wide_hit"]]
    print("missed by judge on wider hits:\n", miss.to_string(index=False, max_colwidth=60))
    fp = d[(d.label == "no_match").values & verdict_match][["company_name", "candidate"]]
    print("judge says match, key says no:\n", fp.to_string(index=False, max_colwidth=60))


if __name__ == "__main__":
    main()
