"""Spec checks for drift tracking (specs/ai-drift-tracking.md). No test calls Anthropic."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_rule_has_one_copy():
    """Spec check 6: the product, the scorer and the gate use one is_clear_exact."""
    from erm import api
    from erm.match import rules
    from eval import compare, offline

    assert api.is_clear_exact is rules.is_clear_exact
    assert compare.is_clear_exact is rules.is_clear_exact
    assert offline.is_clear_exact is rules.is_clear_exact
    for f in [
        "erm/api.py",
        "eval/compare.py",
        "eval/offline.py",
        "eval/run_full_list.py",
    ]:
        src = (ROOT / f).read_text()
        defs = [
            n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
        ]
        assert "is_clear_exact" not in defs, f
        assert "distinctiveness >= 0.75" not in src, f
