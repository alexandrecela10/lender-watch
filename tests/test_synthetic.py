"""The synthetic portfolio (specs/embedded-tools-on-semantic-layer.md, section 1; checks 1 to 5 and 15)."""

import itertools
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data/synthetic"
sys.path.insert(0, str(ROOT / "scripts"))
import make_synthetic as ms

CSVS = [
    "investor.csv",
    "funds.csv",
    "fund_stakes.csv",
    "positions.csv",
    "companies.csv",
    "financials.csv",
    "manager_values.csv",
    "events.csv",
]


def read(name):
    return pd.read_csv(SYN / name, keep_default_na=False)


def test_the_seed_rebuilds_every_file(tmp_path):
    ms.generate(2026, tmp_path)
    for name in CSVS + [f"letters/{i:02d}.md" for i in range(1, 21)]:
        assert (tmp_path / name).read_bytes() == (SYN / name).read_bytes(), name
    # Parquet bytes can differ between library versions, so the content is compared.
    pd.testing.assert_frame_equal(
        pd.read_parquet(tmp_path / "holdings.parquet"),
        pd.read_parquet(SYN / "holdings.parquet"),
    )


def test_nothing_invented_about_a_real_company():
    companies = read("companies.csv")
    real = set(companies[companies.kind == "real"].company_id)
    for name in ["financials.csv", "manager_values.csv", "events.csv"]:
        assert not real & set(read(name).company_id), name
    assert not real & set(pd.read_parquet(SYN / "holdings.parquet").company_id)
    real_names = set(companies[companies.kind == "real"].name)
    for letter in (SYN / "letters").glob("*.md"):
        text = letter.read_text()
        assert not [n for n in real_names if n in text], letter.name


def test_every_row_is_marked_synthetic_and_no_invented_name_is_real():
    for name in CSVS:
        assert (read(name).synthetic.astype(str).str.lower() == "true").all(), name
    assert pd.read_parquet(SYN / "holdings.parquet").synthetic.all()
    invented = list(read("companies.csv").query("kind == 'invented'").name)
    made_up = (
        invented
        + list(read("funds.csv").name)
        + list(read("investor.csv").name)
        + ms.LENDERS
    )
    assert all(n.startswith("Synthetic ") for n in made_up)
    real_world = set(
        pd.read_csv(
            ROOT / "data/sponsors/sponsor_portfolios.csv"
        ).company_name.str.casefold()
    )
    real_world |= set(
        pd.read_csv(
            ROOT / "data/sponsors/sponsor_portfolios.csv"
        ).sponsor.str.casefold()
    )
    real_world |= set(
        pd.read_parquet(
            ROOT / "data/public/holdings.parquet", columns=["lender"]
        ).lender.str.casefold()
    )
    assert not {n.casefold() for n in made_up} & real_world


def test_generator_rules():
    stakes = read("fund_stakes.csv")
    funds = read("funds.csv")
    fof = set(funds[funds.fund_of_funds.astype(str) == "True"].fund_id)
    assert not set(stakes[stakes.owner.isin(fof)].fund_id) & fof, (
        "a fund of funds holds a fund of funds"
    )
    assert (stakes.groupby("fund_id").share.sum() <= 1.0).all()
    loans = pd.read_parquet(SYN / "holdings.parquet")
    fin = read("financials.csv")
    for (cid, q), g in loans.groupby(["company_id", "period"]):
        debt = fin[(fin.company_id == cid) & (fin.quarter == q)].net_debt_usd.iloc[0]
        assert debt >= g.principal.sum() - 0.01, (cid, q)
    assert (fin.revenue_usd > 0).all()
    assert 0 < (fin.ebitda_usd <= 0).mean() < 0.25
    positions = read("positions.csv")
    held = set(positions.company_id)
    assert held == set(read("companies.csv").company_id)
    # A company is held through more than one path when two direct funds hold it, or its fund sits in a fund of funds.
    via_fof = set(stakes[stakes.owner.isin(fof)].fund_id)
    paths = (
        positions[positions.quarter == "2026-06-30"]
        .groupby("company_id")
        .fund_id.apply(lambda f: len(f) + sum(x in via_fof for x in f))
    )
    assert (paths > 1).sum() >= 5


def test_synthetic_lender_rows_fit_lender_watch():
    loans = pd.read_parquet(SYN / "holdings.parquet")
    public_cols = pd.read_parquet(ROOT / "data/public/holdings.parquet").columns
    assert set(public_cols) <= set(loans.columns)
    assert (loans.excluded_reason == "").all()
    assert (
        (loans.fair_value / loans.principal * 100 - loans.pct_par).abs() < 1e-6
    ).all()
    assert loans.inlineurl.str.startswith("synthetic:holdings:").all()
    for _, g in loans.groupby(["company_id", "raw_text"]):
        assert sorted(g.period) == ms.QUARTERS
        a, b = g.sort_values("period").principal
        assert abs(b - a) / a < 0.25


@pytest.fixture(scope="module")
def engine():
    from erm.api import Engine

    folder = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "d.sqlite")
    return Engine(
        holdings_path=str(ROOT / "data/public/holdings.parquet"),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
    )


def test_real_companies_still_qualify(engine):
    chosen = json.loads((SYN / "real_companies.json").read_text())
    assert chosen["data_version"] == engine.data_version
    assert len(chosen["companies"]) == 20
    flagged = 0
    for name in chosen["companies"]:
        june = engine.gather_facts(name)
        assert june["resolution"]["status"] == "matched" and june["facts"], name
        assert engine.gather_facts(name, as_of="2026-03-31")["facts"], name
        flagged += june["flags"]["level"] == "flagged"
    assert flagged >= 3


def test_each_letter_states_its_events_and_nothing_else():
    events = read("events.csv")
    names = dict(read("companies.csv")[["company_id", "name"]].values)
    all_invented = {n for n in names.values() if n.startswith("Synthetic Company")}
    for letter in sorted((SYN / "letters").glob("*.md")):
        text = letter.read_text()
        mine = events[events.letter.astype(str).str.zfill(2) == letter.stem]
        assert len(mine), letter.name
        own = {names[c] for c in mine.company_id}
        mentioned = set(re.findall(r"Synthetic Company \d\d", text))
        assert mentioned == own and own <= all_invented, letter.name
        expected_amounts = set()
        for _, e in mine.iterrows():
            assert ms.day(pd.Timestamp(e.effective).date()) in text
            if e.type == "write_down":
                amount = ms.pct(float(e.size_pct_cost))
                assert amount in text
                expected_amounts.add(amount)
        assert set(re.findall(r"\d+\.\d%", text)) == expected_amounts, letter.name


def test_some_write_downs_land_after_the_manager_reported():
    events = read("events.csv")
    managers = read("manager_values.csv")
    late = [
        e
        for _, e in events[events.type == "write_down"].iterrows()
        for q, reported in ms.MANAGER_REPORTED.items()
        if reported < e.received <= q
    ]
    assert late, "no write-down would change measure 6, so the rule can't be tested"
    assert len(managers) == 80
    assert list(itertools.islice(managers.columns, 0, 4)) == [
        "company_id",
        "quarter",
        "reported",
        "value_pct_cost",
    ]
