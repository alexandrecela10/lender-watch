"""Matching rules shared by the product (erm/api.py) and the evals (eval/compare.py, eval/offline.py).

One copy, so a change to the rule is tested by the same gate that scores it.
"""

from __future__ import annotations


def is_clear_exact(f) -> bool:
    """Skip the judge when the cleaned names are identical and rare. 39 such pairs on the answer key, none wrong."""
    return (
        f.exact_core
        and f.distinctiveness >= 0.75
        and not f.short_name
        and f.left_words == 0
    )
