"""Content checks on the review app (app/review.py) with Streamlit's AppTest. No browser.

The app has two modes. Public mode runs when data/holdings_clean.parquet is absent (a fresh clone, CI, this test):
it offers a firm picker and a box to type names, and no AI judge at all. Local mode runs when the private
holdings file exists: it adds a file uploader and the judge checkbox. AppTest can't drive a file uploader,
so the demo list is typed into the public-mode box, and local mode is started in a temp folder only to read
the judge checkbox. The judge is never switched on here.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from erm import telemetry

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "review.py")
DEMO = ROOT / "data" / "demo" / "sample_list.csv"
SEC = "https://www.sec.gov/"
METRICS = Path(tempfile.mkdtemp()) / "metrics.sqlite"
LANGFUSE_MADE: list = []
TIMEOUT = 300  # the first run on a machine builds the search index (about 100 seconds), later runs reuse it


@pytest.fixture(scope="module")
def checked() -> AppTest:
    """Public mode, demo list typed in, 'Check lender filings' clicked."""
    mp = pytest.MonkeyPatch()
    mp.chdir(ROOT)
    mp.delenv("ANTHROPIC_API_KEY", raising=False)
    mp.setenv("ERM_PUBLIC", "1")
    # Instrumentation: run records go to a temp file, and a Langfuse client must never be made (judge off).
    mp.setenv("ERM_METRICS_PATH", str(METRICS))
    mp.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    mp.setenv("LANGFUSE_SECRET_KEY", "test-only")
    mp.setattr(telemetry, "_make_langfuse", lambda **kw: LANGFUSE_MADE.append(1))
    mp.setattr(telemetry, "_lf_tried", False)
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.text_area[0].input("\n".join(pd.read_csv(DEMO).Company)).run()
    next(b for b in at.button if b.label == "Check lender filings").click().run()
    yield at
    mp.undo()


def results_table(at: AppTest) -> pd.DataFrame:
    return next(d.value for d in at.dataframe if "Flag" in d.value.columns)


def test_app_runs_without_errors(checked):
    assert not checked.exception


def test_knowbe4_is_flagged(checked):
    t = results_table(checked).set_index("Company")
    assert t.loc["KnowBe4", "Flag"] == "Flagged"


def test_unknown_company_shows_as_not_found(checked):
    t = results_table(checked).set_index("Company")
    assert t.loc["Not A Real Company Xyzzy", "What lenders show"] == (
        "No public lender found"
    )


def test_every_loan_row_has_a_filing_link(checked):
    picker = next(s for s in checked.selectbox if s.label.startswith("Pick a company"))
    companies = list(picker.options)
    assert "KnowBe4" in companies
    for name in companies:
        picker.select(name).run()
        loans = next(d for d in checked.dataframe if "Filing" in d.value.columns)
        assert len(loans.value) > 0, name
        assert loans.value["Filing"].str.startswith(SEC).all(), name
        filing = json.loads(loans.proto.columns)["Filing"]  # how the column is shown
        assert filing.get("type_config", {}).get("type") == "link", (
            f"{name}: Filing column is not shown as a link"
        )
        assert not filing.get("hidden"), name
        picker = next(
            s for s in checked.selectbox if s.label.startswith("Pick a company")
        )


def test_public_mode_has_no_judge_checkbox(checked):
    assert not [c for c in checked.checkbox if "Anthropic" in c.label]


def test_local_mode_judge_checkbox_is_off_by_default(checked, monkeypatch):
    """Local mode needs data/holdings_clean.parquet. Use the public holdings under that name in a temp folder."""
    tmp = Path(tempfile.mkdtemp())
    data = tmp / "data"
    data.mkdir()
    shutil.copy(ROOT / "data/public/holdings.parquet", data / "holdings_clean.parquet")
    shutil.copy(ROOT / "data/public/decisions.sqlite", data / "decisions.sqlite")
    shutil.copytree(ROOT / "data/sponsors", data / "sponsors")
    index = Path(tempfile.gettempdir()) / "erm_index.pkl"  # built by the public run
    if index.exists():
        shutil.copy(index, data / "index.pkl")
    monkeypatch.chdir(tmp)
    monkeypatch.delenv("ERM_PUBLIC", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    st.cache_resource.clear()
    shutil.rmtree(tmp)
    assert not at.exception
    judge = [c for c in at.checkbox if c.label.startswith("Send unclear names")]
    assert len(judge) == 1
    assert judge[0].value is False


def test_app_run_writes_one_run_record_and_no_langfuse(checked):
    import sqlite3

    with sqlite3.connect(METRICS) as con:
        rows = con.execute(
            "select source, names_in, judge_on, judge_calls from run_metrics"
        ).fetchall()
    assert rows == [("app", len(pd.read_csv(DEMO)), 0, 0)]
    assert LANGFUSE_MADE == []
