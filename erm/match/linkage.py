"""Probabilistic record linkage (Fellegi-Sunter).

Each feature is turned into a discrete level. For each level we learn two rates from labelled pairs:
  m = how often true matches show this level
  u = how often non-matches show this level
A pair's score is the sum of log2(m/u) over its levels plus the prior log-odds. Positive means "more likely same".

Splink implements the same model at scale, but it expects two tables with several comparable columns and fits
m and u unsupervised. Here one side has only a name and a loose sector, so a small supervised version is clearer.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from erm.match.features import Features


def levels(f: Features) -> dict[str, str]:
    """Discretise features so that each level has enough examples to estimate m and u."""
    return {
        "name": (
            "exact" if f.exact_core
            else "contained" if f.contained
            else "close" if f.name_score >= 85
            else "partial" if f.name_score >= 65
            else "far"
        ),
        "extra": "0" if f.extra_words == 0 else "1" if f.extra_words == 1 else "2+",
        "extra_generic": "0" if f.extra_generic == 0 else "1+",
        "left": "0" if f.left_words == 0 else "1+",
        "trade": str(f.trade_name),
        "distinct": "high" if f.distinctiveness >= 0.75 else "mid" if f.distinctiveness >= 0.5 else "low",
        "shape": "short" if f.short_name else "single" if f.single_word else "multi",
    }


@dataclass
class LinkageModel:
    weights: dict[str, dict[str, float]]
    prior_log2_odds: float

    @classmethod
    def fit(cls, feats: list[Features], labels: list[bool], smoothing: float = 0.5) -> "LinkageModel":
        pos = Counter()
        neg = Counter()
        seen = defaultdict(set)
        for f, y in zip(feats, labels):
            for k, v in levels(f).items():
                seen[k].add(v)
                (pos if y else neg)[(k, v)] += 1
        n_pos, n_neg = sum(labels), len(labels) - sum(labels)
        weights: dict[str, dict[str, float]] = defaultdict(dict)
        for k, vals in seen.items():
            d = len(vals)
            for v in vals:
                m = (pos[(k, v)] + smoothing) / (n_pos + smoothing * d)
                u = (neg[(k, v)] + smoothing) / (n_neg + smoothing * d)
                weights[k][v] = math.log2(m / u)
        prior = math.log2((n_pos + 1) / (n_neg + 1))
        return cls(dict(weights), prior)

    def score(self, f: Features) -> float:
        return self.prior_log2_odds + sum(self.weights.get(k, {}).get(v, 0.0) for k, v in levels(f).items())

    def explain(self, f: Features) -> dict[str, float]:
        return {f"{k}={v}": round(self.weights.get(k, {}).get(v, 0.0), 2) for k, v in levels(f).items()}
