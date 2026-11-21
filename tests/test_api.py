import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from erm.connectors.bdc import enrich
from erm.api import Engine, fingerprint, lender_data_label
from erm.retrieve import Index
from erm.store import Store


def out(status, facts=(), excluded=None):
    return {
        "resolution": {"status": status},
        "facts": list(facts),
        "excluded": excluded or {},
    }


def test_unclear_match_never_reads_as_no_data():
    assert lender_data_label(out("needs_review")) == "To confirm"
    assert (
        lender_data_label(out("needs_review", [{}])) == "Found, more matches to confirm"
    )


def test_rows_with_unusable_amounts_never_read_as_no_data():
    assert "can't be used" in lender_data_label(
        out("matched", excluded={"amounts don't line up": 2})
    )


def test_no_data_is_stated_as_no_filing_lender():
    assert lender_data_label(out("not_found")) == "No public lender found"


def test_review_queue_is_limited_to_the_current_list(tmp_path):
    s = Store(tmp_path / "d.sqlite")
    s.save("Foundation", "foundation risk", "unsure", "judge")
    s.save("Orion Group", "orion services", "unsure", "judge")
    assert [d.name for d in s.pending({"Orion Group"})] == ["Orion Group"]
    assert len(s.pending()) == 2


def test_a_persons_answer_can_be_changed_and_automation_cannot_overwrite_it(tmp_path):
    s = Store(tmp_path / "d.sqlite")
    d = s.save("Orion Group", "orion services", "unsure", "judge")
    assert s.review(d.pair_id, True).verdict == "match"
    assert s.review(d.pair_id, False).verdict == "no_match"
    assert (
        s.save("Orion Group", "orion services", "match", "judge").verdict == "no_match"
    )


def test_foreign_loan_in_local_currency_is_left_out_not_read_as_a_markdown():
    # 123Dentist: principal in Canadian dollars, cost and value in US dollars. Reads about 70% of par without this rule.
    h = pd.DataFrame(
        [
            dict(
                raw_text="123Dentist Inc 2 | First Lien",
                principal=55904000.0,
                cost=42891000.0,
                fair_value=39351000.0,
                maturity_col=None,
                adsh="a",
            )
        ]
    )
    assert enrich(h).excluded_reason[0] == "amounts don't line up"
    near_par = h.assign(cost=55000000.0, fair_value=50000000.0)
    assert enrich(near_par).excluded_reason[0] == ""


# --- Choosing the quarter (specs/engine-in-excel-and-claude.md, section 2) ---

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/public/holdings.parquet"


@pytest.fixture(scope="module")
def quarters_engine():
    folder = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "d.sqlite")
    return Engine(
        holdings_path=str(PUBLIC),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
    )


def test_both_held_quarters_can_be_asked_for(quarters_engine):
    e = quarters_engine
    assert e.periods() == ["2026-03-31", "2026-06-30"]
    june = e.gather_facts("KnowBe4")
    assert (june["as_of"], june["compared_with"]) == ("2026-06-30", "2026-03-31")
    assert june["facts"] and all(f["period"] == "2026-06-30" for f in june["facts"])
    march = e.gather_facts("KnowBe4", as_of="2026-03-31")
    assert (march["as_of"], march["compared_with"]) == ("2026-03-31", None)
    assert march["facts"] and all(f["period"] == "2026-03-31" for f in march["facts"])
    assert all(f["change"] is None for f in march["facts"])
    assert june["data_version"] == march["data_version"] == fingerprint(PUBLIC)


def test_an_unknown_quarter_is_refused_and_names_the_quarters_held(quarters_engine):
    with pytest.raises(ValueError, match="2026-03-31, 2026-06-30"):
        quarters_engine.gather_facts("KnowBe4", as_of="2025-12-31")


def test_june_index_is_exactly_what_the_engine_built_before_quarters(quarters_engine):
    """Matching on 30 June must not move: the per-quarter index is built from that quarter's rows, as before."""
    holdings = quarters_engine.holdings
    before = Index.build(holdings[holdings.period == "2026-06-30"], semantic=False)
    after = quarters_engine.index_for("2026-06-30")
    assert after.tokens == before.tokens
    assert len(after.holdings) == len(before.holdings) == 66494


def test_changed_data_builds_a_new_index(tmp_path):
    h = pd.read_parquet(PUBLIC)
    small = h[h.raw_text.str.contains("KnowBe4", regex=False)]
    data = tmp_path / "h.parquet"
    small.to_parquet(data, index=False)
    cache = tmp_path / "idx.pkl"
    first = Engine(str(data), str(tmp_path / "d.sqlite"), str(cache))
    small.head(3).to_parquet(data, index=False)
    second = Engine(str(data), str(tmp_path / "d.sqlite"), str(cache))
    assert first.data_version != second.data_version
    assert len(second.index_for(second.latest()).holdings) <= 3
    assert len(list(tmp_path.glob("idx-*.pkl"))) >= 2


def test_stray_dates_are_not_quarters(tmp_path):
    """The full SEC file has 10 rows dated 31 December 2026 and funds reporting at odd month-ends."""
    h = pd.read_parquet(PUBLIC)
    small = h[h.raw_text.str.contains("KnowBe4", regex=False)]
    stray = small.head(1).assign(period="2026-12-31")
    odd_month = small.head(1).assign(period="2026-05-31")
    data = tmp_path / "h.parquet"
    pd.concat([small, stray, odd_month]).to_parquet(data, index=False)
    e = Engine(str(data), str(tmp_path / "d.sqlite"), str(tmp_path / "idx.pkl"))
    assert e.periods() == ["2026-03-31", "2026-06-30"]
    assert e.gather_facts("KnowBe4")["as_of"] == "2026-06-30"
