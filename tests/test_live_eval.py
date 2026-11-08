"""Spec checks for drift tracking (specs/ai-drift-tracking.md). No test calls Anthropic."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_rule_has_one_copy():
    """Spec check 6: the product, the scorer and the gate use one is_clear_exact. This covers placement;
    `make evals` covers the rule's results (precision 1.000, recall 0.936)."""
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


# D2: the live check with a fake judge. Nothing is sent anywhere.
import json

import anthropic
import httpx2 as httpx
import pandas as pd
import pytest

from eval import live

STORED = dict(
    pd.read_csv(ROOT / "data/eval/judge_results.csv")[
        ["pair_id", "verdict"]
    ].itertuples(index=False)
)
NAMES = sorted(
    set(pd.read_csv(ROOT / "data/eval/scored_pairs.csv").company_name.dropna()),
    key=len,
    reverse=True,
)


def fake(verdicts=None, cost=0.004, model="claude-opus-5-5", fail=()):
    verdicts = verdicts or STORED

    def ask(r):
        if int(r.pair_id) in fail:
            raise anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com")
            )
        return verdicts[int(r.pair_id)], model, cost

    return ask


@pytest.fixture
def at_root(monkeypatch):
    monkeypatch.chdir(ROOT)


def run(tmp_path, judge, *extra):
    out = tmp_path / "summary.md"
    code = live.main(["--summary", str(out), *extra], judge=judge)
    return code, (out.read_text() if out.exists() else "")


def flipped(n):
    d = live.load()
    ask, _ = live.pairs_to_ask(d)
    wrong = d[
        ask & (d.label == "no_match").values & (d.verdict == "no_match").values
    ].pair_id.astype(int)
    return {**STORED, **{p: "match" for p in wrong[:n]}}


def test_dry_run_lists_pair_ids_no_names(at_root, capsys):
    assert live.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("145 pairs to ask")
    assert not [n for n in NAMES if len(n) > 3 and n in out]


def test_fake_judge_with_stored_answers_matches_the_gate(at_root, tmp_path):
    code, text = run(tmp_path, fake())
    m = live.parse_last(text)
    assert code == 0 and m["status"] == "PASS"
    assert (m["precision"], m["recall"], m["fp"]) == (1.0, 0.936, 0)


def test_six_wrong_pairs_fail_one_warns(at_root, tmp_path):
    code, text = run(tmp_path, fake(flipped(6)))
    assert code == 1 and live.parse_last(text)["status"] == "FAIL"
    (tmp_path / "one").mkdir()
    code, text = run(tmp_path / "one", fake(flipped(1)))
    assert code == 0 and "Passed, with a warning: 1 wrong match." in text


def test_cost_cap_stops_the_run(at_root, tmp_path):
    code, text = run(tmp_path, fake(cost=0.05))
    m = live.parse_all(text)[-1]
    assert code == 1 and m["status"] == "INCOMPLETE" and "cost cap reached" in text
    assert m["calls"] == 60 and m["calls"] < 250


def test_unknown_cost_counts_toward_the_cap(at_root, tmp_path):
    code, text = run(tmp_path, fake(cost=None, model="some-fallback-model"))
    assert code == 1 and live.parse_all(text)[-1]["calls"] == 60


def test_no_live_flag_makes_no_call(at_root, tmp_path, capsys):
    out = tmp_path / "summary.md"
    assert live.main(["--summary", str(out)]) == 0
    assert "skipped: pass --live" in capsys.readouterr().out
    assert not out.exists()


def test_no_key_skips_and_posts_nothing(at_root, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    out = tmp_path / "summary.md"
    assert live.main(["--live", "--summary", str(out)]) == 0
    assert "skipped: no ANTHROPIC_API_KEY" in capsys.readouterr().out
    assert not out.exists()


def test_no_company_name_in_any_output(at_root, tmp_path, capsys):
    _, text = run(tmp_path, fake(flipped(1)))
    shown = text + capsys.readouterr().out
    assert not [n for n in NAMES if len(n) > 3 and n in shown]


def test_history_comment_parses_back_and_compares(at_root, tmp_path):
    _, first = run(tmp_path, fake())
    last = tmp_path / "last.md"
    last.write_text("Some text\n" + first)
    second = tmp_path / "second.md"
    live.main(["--summary", str(second), "--last", str(last)], judge=fake(flipped(1)))
    text = second.read_text()
    assert "Wrong matches: 1. Last run: 0." in text
    assert "right 99.4% of the time. Minimum: 97%. Last run: 100.0%." in text
    assert "Passed, with a warning: 1 wrong match." in text


def test_errors_mark_the_run_error_not_fail(at_root, tmp_path):
    d = live.load()
    ask, _ = live.pairs_to_ask(d)
    failing = set(d.pair_id[ask].astype(int)[:20])
    code, text = run(tmp_path, fake(fail=failing))
    m = live.parse_all(text)[-1]
    assert code == 1 and m["status"] == "ERROR" and m["errors"] > 2


def test_a_few_errors_are_left_out_of_the_scores(at_root, tmp_path):
    d = live.load()
    ask, _ = live.pairs_to_ask(d)
    failing = set(d.pair_id[ask].astype(int)[:5])
    code, text = run(tmp_path, fake(fail=failing))
    m = live.parse_last(text)
    assert (
        code == 0 and m["status"] == "PASS" and m["errors"] == 5 and m["calls"] == 145
    )


def test_reference_counts_changed_verdicts(at_root, tmp_path):
    ref = tmp_path / "ref.csv"
    live.main(["--write-reference", str(ref)], judge=fake())
    assert len(pd.read_csv(ref)) == 145
    live.REFERENCE, old = str(ref), live.REFERENCE
    try:
        _, text = run(tmp_path, fake(flipped(2)))
    finally:
        live.REFERENCE = old
    assert "Answers changed since the reference run: 2 of 145." in text
    assert json.loads(text.split(live.MARKER)[1].split(" -->")[0])["fp"] == 2


def test_parse_last_takes_the_last_result():
    a = live.MARKER + '{"status": "PASS", "fp": 0} -->'
    b = live.MARKER + '{"status": "FAIL", "fp": 7} -->'
    c = live.MARKER + '{"status": "INCOMPLETE", "calls": 60} -->'
    assert live.parse_last(f"run 1\n{a}\nrun 2\n{b}\n")["fp"] == 7
    assert live.parse_last(f"{a}\n{c}\n")["fp"] == 0
    assert live.parse_last("no marker") is None
    bad = live.MARKER + '{"status": "PASS", "fp": "999"} -->'
    assert live.parse_last(f"{a}\n{bad}\n")["fp"] == 0
