"""Find candidate holdings for a listed company name. Four independent ways to search, so a pool isn't biased to one."""

from __future__ import annotations

import collections
from dataclasses import dataclass

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer

from erm.match.features import GENERIC
from erm.textparse import Mention, borrowers_in, core, find_mention, name_pattern, norm


def name_variants(name: str) -> list[str]:
    """Search forms of a listed name: its core, plus the core without a trailing generic word.
    "First Eagle Investments" also searches "first eagle". A variant needs two words left, to stay distinctive."""
    c = core(name)
    out = [c] if c else []
    toks = c.split()
    if len(toks) >= 3 and toks[-1] in GENERIC | {"investments", "investment", "advisors"}:
        out.append(" ".join(toks[:-1]))
    return out


def compact_hit(name: str, candidate: str) -> bool:
    """True when the names agree once spaces are removed: "AlertMedia" and "Alert Media, Inc."."""
    c, b = core(name).replace(" ", ""), core(candidate).replace(" ", "")
    return len(c) >= 6 and c == b


RARE_ROWS = 150  # a first word in fewer holdings than this is distinctive enough to search alone


@dataclass
class Index:
    """Search structures over one period of holdings."""

    holdings: pd.DataFrame  # one period, positional index
    tokens: dict[str, set[int]]
    borrowers: list[str]
    borrower_rows: dict[str, list[int]]
    tfidf: TfidfVectorizer | None = None
    tfidf_matrix: object = None
    embedder: object = None
    embeddings: np.ndarray | None = None

    @classmethod
    def build(cls, holdings: pd.DataFrame, semantic: bool = True) -> "Index":
        h = holdings.reset_index(drop=True)
        tokens: dict[str, set[int]] = collections.defaultdict(set)
        rows: dict[str, list[int]] = collections.defaultdict(list)
        for i, raw in enumerate(h.raw_text):
            for t in set(norm(raw).split()):
                tokens[t].add(i)
            for b in borrowers_in(raw):
                rows[b].append(i)
        idx = cls(h, dict(tokens), sorted(rows), dict(rows))
        if semantic:
            idx.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), min_df=1, lowercase=True)
            idx.tfidf_matrix = idx.tfidf.fit_transform([norm(b) for b in idx.borrowers])
            from model2vec import StaticModel

            idx.embedder = StaticModel.from_pretrained("minishlab/potion-base-8M")
            e = idx.embedder.encode([norm(b) for b in idx.borrowers])
            idx.embeddings = e / np.clip(np.linalg.norm(e, axis=1, keepdims=True), 1e-9, None)
        return idx

    def rarest_rows(self, core_name: str) -> set[int]:
        toks = core_name.split()
        best = min(toks, key=lambda t: len(self.tokens.get(t, ())))
        return self.tokens.get(best, set())

    def name_hits(self, name: str) -> list[tuple[int, Mention]]:
        """Every holding whose text contains the name's core as whole words."""
        out: dict[int, Mention] = {}
        variants = name_variants(name)
        first = core(name).split()[0] if core(name) else ""
        # A rare, long first word finds renamed combinations: "Jeppesen ForeFlight" -> "Jeppesen Holdings".
        if len(core(name).split()) >= 2 and len(first) >= 6 and first not in GENERIC and len(self.tokens.get(first, ())) <= RARE_ROWS:
            variants.append(first)
        for c in variants:
            pat = name_pattern(c)
            for i in self.rarest_rows(c):
                if i not in out and (m := find_mention(self.holdings.raw_text.iloc[i], pat)):
                    out[i] = m
        for b in self.borrowers:  # spacing differences only
            if compact_hit(name, b):
                pat = name_pattern(core(b))
                for i in self.borrower_rows[b]:
                    if i not in out and (m := find_mention(self.holdings.raw_text.iloc[i], pat)):
                        out[i] = m
        return list(out.items())

    def fuzzy_borrowers(self, name: str, k: int = 5) -> list[str]:
        return [r[0] for r in process.extract(core(name), self.borrowers, scorer=fuzz.WRatio, processor=norm, limit=k)]

    def tfidf_borrowers(self, name: str, k: int = 5) -> list[str]:
        q = self.tfidf.transform([core(name)])
        s = (self.tfidf_matrix @ q.T).toarray().ravel()
        return [self.borrowers[i] for i in np.argsort(-s)[:k] if s[i] > 0]

    def embedding_borrowers(self, name: str, context: str = "", k: int = 5) -> list[str]:
        e = self.embedder.encode([norm(f"{name} {context}")])[0]
        e = e / max(np.linalg.norm(e), 1e-9)
        s = self.embeddings @ e
        return [self.borrowers[i] for i in np.argsort(-s)[:k]]
