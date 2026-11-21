"""Agreed measures (specs/embedded-tools-on-semantic-layer.md, section 2; checks 6 to 9, 11, 12 and 16)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from erm import assist, semantic
from erm.api import fingerprint
from erm.connectors.bdc import PROFILE

ROOT = Path(__file__).resolve().parents[1]
REAL = json.loads((ROOT / "data/synthetic/real_companies.json").read_text())[
    "companies"
]


@pytest.fixture(scope="module")
def proto():
    return semantic.Prototype()


def test_definitions_load_and_are_complete():
    measures = semantic.load_measures()
    assert len(measures) == 6
    for m in measures.values():
        assert all(m[f] not in (None, "") for f in semantic.FIELDS)


def test_a_definition_with_a_missing_function_is_refused(tmp_path):
    bad = tmp_path / "m.yaml"
    bad.write_text(
        "- {id: x, name: X, definition: d, unit: usd, applies_to: both, owner: o, version: 1, compute: nope, explain: none}\n"
    )
    with pytest.raises(TypeError, match="no function nope"):
        semantic.load_measures(bad)


def test_look_through_cost_follows_every_path(proto):
    """We own 20% of a fund of funds, which owns 10% of a fund that paid $40m: our cost is $0.8m."""
    p = proto.portfolio
    saved = p.stakes, p.positions
    try:
        p.stakes = pd.DataFrame(
            [
                {"owner": "P1", "fund_id": "F7", "share": 0.2},
                {"owner": "F7", "fund_id": "F3", "share": 0.1},
            ]
        )
        p.positions = pd.DataFrame(
            [
                {
                    "fund_id": "F3",
                    "company_id": "X",
                    "quarter": "2026-06-30",
                    "cost_usd": 40_000_000,
                }
            ]
        )
        p.weights = p._look_through()
        assert p.cost("X", "2026-06-30")[0] == pytest.approx(800_000)
    finally:
        p.stakes, p.positions = saved
        p.weights = p._look_through()


def test_cost_in_flagged_has_a_row_with_sources_for_all_60(proto):
    ids = list(proto.portfolio.companies.company_id)
    out = proto.get_measure("cost_in_flagged", ids)
    assert len(out["rows"]) == 60
    assert all(r["value"] is not None and r["sources"] for r in out["rows"])
    assert out["total"]["value"] == pytest.approx(sum(r["value"] for r in out["rows"]))
    assert out["total"]["not_checked"] == 0


def test_share_uses_the_whole_portfolio_whatever_was_asked(proto):
    alone = proto.get_measure("share_cost_flagged", ["KnowBe4"])["rows"][0]["value"]
    among = proto.get_measure(
        "share_cost_flagged", ["KnowBe4", "Synthetic Company 01"]
    )["rows"][0]["value"]
    assert alone == among > 0


@pytest.mark.parametrize("measure", ["debt_to_ebitda", "manager_lender_gap"])
def test_private_data_measures_give_no_number_for_a_real_company(proto, measure):
    row = proto.get_measure(measure, ["KnowBe4"])["rows"][0]
    assert row["value"] is None and row["not_available"] == semantic.NOT_REAL
    assert row["sources"] == []


def test_unknown_company_and_unknown_measure(proto):
    row = proto.get_measure("lender_value", ["Not A Company"])["rows"][0]
    assert row["value"] is None and row["not_available"] == semantic.NOT_IN_PORTFOLIO
    with pytest.raises(ValueError, match="No measure"):
        proto.get_measure("nope", ["KnowBe4"])


def test_negative_ebitda_is_not_meaningful(proto):
    f = proto.portfolio.financials
    cid = f[(f.ebitda_usd <= 0) & (f.quarter == "2026-06-30")].company_id.iloc[0]
    row = proto.get_measure("debt_to_ebitda", [cid])["rows"][0]
    assert row["value"] is None and row["not_available"].startswith("Not meaningful")


def test_lender_change_is_not_available_in_the_first_quarter(proto):
    row = proto.get_measure("lender_change", ["KnowBe4"], as_of="2026-03-31")["rows"][0]
    assert row["value"] is None and "No earlier quarter" in row["not_available"]


@pytest.mark.parametrize("quarter", ["2026-03-31", "2026-06-30"])
def test_real_lender_measures_equal_lender_watch(proto, quarter):
    for name in REAL:
        flags = proto.engine.gather_facts(name, as_of=quarter)["flags"]
        value = proto.get_measure("lender_value", [name], as_of=quarter)["rows"][0][
            "value"
        ]
        assert value == pytest.approx(flags["weighted_pct_par"]), name
        if quarter == "2026-06-30" and flags["weighted_change"] is not None:
            change = proto.get_measure("lender_change", [name])["rows"][0]["value"]
            assert change == pytest.approx(flags["weighted_change"]), name


def test_lender_watch_is_unchanged_by_the_prototype(proto):
    assert proto.engine.data_version == fingerprint(
        ROOT / "data/public/holdings.parquet"
    )
    assert "Synthetic" not in " ".join(proto.engine.holdings.raw_text.head(100000))
    row = assist.check_list(proto.engine, [{"name": "Synthetic Company 01"}], PROFILE)[
        "rows"
    ][0]
    # The name search may offer an ordinary public company with "Company" in its name, never a synthetic row.
    # (The public data holds a real borrower called Synthetic Sciences; it may be offered for a person to confirm.)
    invented = set(proto.portfolio.companies.query("kind == 'invented'").name)
    assert not {x["listed_as"] for x in row["to_confirm"]} & invented
    assert not row["loans"]
    assert not proto.engine.holdings.raw_text.str.contains("Synthetic Company").any()


def test_every_row_using_a_synthetic_source_says_so(proto):
    ids = list(proto.portfolio.companies.company_id)
    for measure in proto.measures:
        for r in proto.get_measure(measure, ids)["rows"]:
            kinds = {s["kind"] for s in r["sources"]}
            assert kinds <= {"filing", "synthetic"}
            assert r["synthetic"] == ("synthetic" in kinds), (measure, r["company"])
            for s in r["sources"]:
                prefix = (
                    "synthetic:" if s["kind"] == "synthetic" else "https://www.sec.gov/"
                )
                assert s["ref"].startswith(prefix), (measure, r["company"], s)
    # Real lender figures come from filings only.
    real = proto.get_measure("lender_value", ["KnowBe4"])["rows"][0]
    assert real["synthetic"] is False and real["sources"]


# --- Claude and Excel, on this computer only (checks 10 and 19) ---


def test_excel_route_and_claude_tool_give_identical_rows():
    import tempfile as tf

    from starlette.testclient import TestClient

    from erm import mcp_server, service

    tool = mcp_server.mcp._tool_manager.get_tool("get_measure").fn
    ids = ["KnowBe4", "Synthetic Company 01", "Synthetic Company 04", "Not A Company"]
    app = service.create_app(None, "http://localhost:8770", Path(tf.mkdtemp()))
    with TestClient(app) as c:
        for measure in semantic.load_measures():
            via_excel = c.post(
                "/api/measure", json={"measure": measure, "companies": ids}
            ).json()
            assert via_excel == tool(measure, ids), measure
        bad = c.post("/api/measure", json={"measure": "nope", "companies": ids})
        assert bad.status_code == 400


def test_the_tool_description_lists_every_measure():
    from erm import prototype_tools

    text = prototype_tools.measure_description()
    assert all(m in text for m in semantic.load_measures())


def test_hosted_service_never_loads_the_prototype():
    import subprocess
    import sys

    code = (
        "import sys, tempfile, pathlib\n"
        "from starlette.testclient import TestClient\n"
        "from erm import service\n"
        "from tests import fake_provider as fp\n"
        "app = service.create_app(fp.config(), fp.BASE, pathlib.Path(tempfile.mkdtemp()))\n"
        "with TestClient(app, base_url='https://testserver') as c:\n"
        "    r = c.post('/api/measure', json={'measure': 'lender_value', 'companies': ['KnowBe4']}, headers=fp.bearer())\n"
        "    assert r.status_code == 404 and 'this computer only' in r.json()['error'], r.text\n"
        "assert 'erm.semantic' not in sys.modules, 'hosted service loaded the prototype'\n"
        "print('ok')\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[
        -2000:
    ]
