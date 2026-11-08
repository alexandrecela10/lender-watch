"""The range check on names needing a person's review. All run rows here are made up."""

import csv
import re
from pathlib import Path

import pytest

from erm.telemetry import write_metrics
from eval import bands

CFG = bands.load_config()


def row(i, names, review, **over):
    return {
        "request_id": f"r{i}",
        "session_id": "s",
        "source": "cli",
        "started_at": f"2026-11-{i + 1:02d}T00:00:00Z",
        "judge_on": 1,
        "status": "ok",
        "names_in": names,
        "names_matched": 0,
        "names_needing_review": review,
        "flagged": 0,
        "worth_a_look": 0,
        "duration_ms": 1,
        "judge_calls": 0,
        "judge_cost_usd": 0.0,
    } | over


def db_with(tmp_path, rows):
    db = tmp_path / "m.sqlite"
    for r in rows:
        write_metrics(db, r)
    return db


def all_output(tmp_path, r, text):
    drafts = [p.read_text() for p in (tmp_path / "out").glob("*.md")]
    return "\n".join([text, *drafts])


def test_config_is_labelled_provisional_with_its_source():
    assert CFG["status"] == "provisional"
    raw = bands.BANDS_PATH.read_text()
    assert "PROVISIONAL" in raw
    assert "full_results.csv" in CFG["baseline"]["source"]


def test_baseline_matches_the_saved_full_run():
    with Path("data/eval/full_results.csv").open() as f:
        statuses = [r["status"] for r in csv.DictReader(f)]
    assert CFG["baseline"]["names"] == len(statuses)
    assert CFG["baseline"]["names_needing_review"] == statuses.count("needs_review")


def test_inside_the_range(tmp_path):
    db = db_with(tmp_path, [row(i, 30, 3) for i in range(10)])  # 10%
    r, text = bands.run(db, CFG, tmp_path / "out")
    assert r.state == bands.INSIDE
    assert not r.breached
    assert "No action needed" in text
    assert not (tmp_path / "out").exists()


def test_breach_high_writes_a_draft_intent(tmp_path):
    db = db_with(tmp_path, [row(i, 30, 9) for i in range(10)])  # 30%
    r, text = bands.run(db, CFG, tmp_path / "out")
    assert r.state == bands.HIGH
    assert "Action needed" in text
    draft = next((tmp_path / "out").glob("*.md")).read_text()
    assert "Status: draft" in draft
    assert "inferred from public signals" in draft
    for section in (
        "## Problem",
        "## Proposed outcome",
        "What should change",
        "What must not get worse",
        "## Affected users and systems",
        "## Constraints",
        "## Open questions",
    ):
        assert section in draft
    problem = draft.split("## Problem")[1].split("## ")[0]
    bullets = [x for x in problem.splitlines() if x.startswith("- ")]
    assert 3 <= len(bullets) <= 5
    assert "`" not in problem
    assert "/" not in problem
    assert "SIMULATED" not in draft


def test_breach_low_is_reported_as_too_few_reaching_a_person(tmp_path):
    db = db_with(tmp_path, [row(i, 30, 0) for i in range(10)])
    r, text = bands.run(db, CFG, tmp_path / "out")
    assert r.state == bands.LOW
    assert "too few names" in text


def test_no_runs_yet_no_file_and_empty_table(tmp_path):
    r, text = bands.run(tmp_path / "absent.sqlite", CFG, tmp_path / "out")
    assert r.state == bands.NO_RUNS
    assert "no finished runs" in text

    db = db_with(tmp_path, [row(1, 50, 1, judge_on=0)])
    assert bands.check(db, CFG).state == bands.NO_RUNS


def test_too_few_names_makes_no_judgement(tmp_path):
    db = db_with(tmp_path, [row(1, 6, 5)])
    r, text = bands.run(db, CFG, tmp_path / "out")
    assert r.state == bands.TOO_FEW
    assert "No check made" in text
    assert not r.breached


def test_failed_and_judge_off_runs_are_left_out(tmp_path):
    rows = [row(i, 30, 3) for i in range(10)]
    rows += [row(20, 100, 90, judge_on=0), row(21, 100, 90, status="error")]
    assert bands.check(db_with(tmp_path, rows), CFG).state == bands.INSIDE


def test_only_the_latest_runs_are_pooled(tmp_path):
    old = [
        row(
            i,
            30,
            3,
            request_id=f"old{i}",
            started_at=f"2026-10-{i + 1:02d}T00:00:00Z",
        )
        for i in range(25)
    ]
    new = [row(i, 30, 9) for i in range(20)]
    r = bands.check(db_with(tmp_path, old + new), CFG)
    assert r.runs == CFG["window_runs"]
    assert r.state == bands.HIGH


def test_no_company_name_can_appear_in_the_output(tmp_path):
    secret = "Zyxwv Holdings LLC"
    rows = [
        row(i, 30, 9, source=secret, session_id=secret, request_id=f"{secret} {i}")
        for i in range(10)
    ]
    r, text = bands.run(db_with(tmp_path, rows), CFG, tmp_path / "out")
    assert r.breached
    output = all_output(tmp_path, r, text)
    assert secret not in output
    assert "Zyxwv" not in output

    with Path("data/sponsors/sponsor_portfolios.csv").open() as f:
        companies = [x["company_name"] for x in csv.DictReader(f)]
    assert companies
    for name in companies:
        assert not re.search(rf"\b{re.escape(name)}\b", output), name


def test_plain_words_in_the_output(tmp_path):
    db = db_with(tmp_path, [row(i, 30, 9) for i in range(10)])
    r, text = bands.run(db, CFG, tmp_path / "out")
    output = all_output(tmp_path, r, text).lower()
    for word in ("threshold", "sigma", "standard deviation", "—"):
        assert word not in output
    assert not re.search(
        r"\bbands?\b",
        output.replace("eval/bands.py", "").replace("evals/bands.yaml", ""),
    )


def test_simulated_breach_says_so_everywhere(tmp_path):
    r, text = bands.simulate(CFG, tmp_path / "out")
    assert r.simulated and r.state == bands.HIGH
    assert text.startswith("SIMULATED")
    draft = next((tmp_path / "out").glob("*.md"))
    assert draft.name.startswith("SIMULATED")
    content = draft.read_text()
    assert content.startswith("# SIMULATED")
    assert bands.SIMULATED_BANNER in content


def test_simulation_never_opens_the_real_records(tmp_path, monkeypatch):
    real = db_with(tmp_path, [row(i, 20, 2) for i in range(10)])
    monkeypatch.setenv("ERM_METRICS_PATH", str(real))
    before = real.read_bytes()
    r, _ = bands.simulate(CFG, tmp_path / "out")
    assert (r.names, r.needing_review) == (300, 80)  # the made-up runs only
    assert real.read_bytes() == before


def test_simulated_draft_is_refused_in_the_intent_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="SIMULATED"):
        bands.write_draft(
            bands.Result(bands.HIGH, 1, 100, 50, 0.1, 0.0, 0.2, True, "a", "b"),
            CFG,
            Path("intent"),
        )
    assert not (tmp_path / "intent").exists()


def test_pull_request_option_is_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bands,
        "open_pull_request",
        lambda *a, **k: pytest.fail("must not open a pull request by default"),
    )
    db = db_with(tmp_path, [row(i, 30, 9) for i in range(10)])
    r, _ = bands.run(db, CFG, tmp_path / "out")
    assert r.breached

    monkeypatch.setenv("ERM_METRICS_PATH", str(db))
    monkeypatch.setattr("sys.argv", ["bands", "--draft-dir", str(tmp_path / "o2")])
    with pytest.raises(SystemExit) as e:
        bands.main()
    assert e.value.code == 1


def test_simulated_draft_never_becomes_a_pull_request():
    calls = []
    r = bands.Result(bands.HIGH, 1, 100, 50, 0.1, 0.0, 0.2, True, "a", "b")
    with pytest.raises(SystemExit, match="SIMULATED"):
        bands.open_pull_request(Path("x.md"), r, run=lambda *a, **k: calls.append(a))
    assert calls == []
