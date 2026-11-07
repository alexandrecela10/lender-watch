"""Comparison features for a (listed company, candidate borrower) pair.

Nothing here is specific to BDCs: a candidate is any borrower or entity string from any source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rapidfuzz import fuzz

from erm.textparse import core, norm

# Words common enough in company names that sharing only them says little.
GENERIC = frozenset(
    """partners solutions services service systems software technologies technology health healthcare care financial
    capital management consulting group holdings products industries brands network networks data digital analytics
    global international national american united first new one""".split()
)


@dataclass(frozen=True)
class Features:
    name_score: float  # 0-100, listed core vs candidate core
    exact_core: bool  # cleaned names identical
    contained: bool  # listed core appears whole inside the candidate
    extra_words: int  # candidate words beyond the listed core, ignoring generic words
    extra_generic: int  # candidate words beyond the listed core that are generic
    left_words: int  # name words before the hit ("wheel" in "Wheel Pros")
    trade_name: bool  # hit is a stated trade name in brackets
    distinctiveness: (
        float  # rarity of the listed core's rarest word across the source, 0-1
    )
    single_word: bool
    short_name: bool  # four letters or fewer


def word_rarity(word: str, doc_freq: dict[str, int], total: int) -> float:
    """Inverse document frequency scaled to 0-1. An unseen word counts as fully rare."""
    df = doc_freq.get(word, 0)
    return min(1.0, math.log((total + 1) / (df + 1)) / math.log(total + 1))


def compute(
    listed: str,
    candidate: str,
    doc_freq: dict[str, int],
    total: int,
    left: tuple[str, ...] = (),
    right: tuple[str, ...] | None = None,
    trade_name: bool = False,
) -> Features:
    lc, cc = core(listed), core(candidate)
    lt, ct = lc.split(), cc.split()
    contained = f" {lc} " in f" {norm(candidate)} "
    if right is None:
        extra = [t for t in ct if t not in set(lt)]
    else:
        extra = list(right)
    return Features(
        name_score=fuzz.token_sort_ratio(lc, cc),
        exact_core=lc == cc,
        contained=contained,
        extra_words=sum(t not in GENERIC for t in extra),
        extra_generic=sum(t in GENERIC for t in extra),
        left_words=len(left),
        trade_name=trade_name,
        distinctiveness=max((word_rarity(t, doc_freq, total) for t in lt), default=0.0),
        single_word=len(lt) == 1,
        short_name=len(lc.replace(" ", "")) <= 4,
    )
