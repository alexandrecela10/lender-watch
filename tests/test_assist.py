"""The layer between where people work and the engine, the MCP tools on it, and the Analyst Desk's actions.

Runs on small fixtures with no outside calls, except the shared engine fixture, which reads the public sample.
"""

import io
import json
import logging
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from app.desk import assistant
from app.desk.server import Desk, demo_workbook
from erm import assist, mcp_server, telemetry
from erm.api import Engine
from erm.connectors.bdc import PROFILE

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = [
    ["Company", "Owner", "Sector"],
    ["KnowBe4", "Vista", "Security"],
    ["Foundation", "Thoma Bravo", "Applications"],
    ["Exabeam", "Thoma Bravo", "Cybersecurity"],
]
TAPE = [
    ["Lender", "Borrower (as filed)", "Value"],
    ["Fund A", "KnowBe4, Inc. | Education", 78.5],
    ["Fund B", "Foundation Risk Partners, Corp. | First lien", 100.0],
    ["Fund C", "LogRhythm, Inc. | First lien", 90.2],
]


@pytest.fixture(scope="module")
def engine():
    folder = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "d.sqlite")
    return Engine(
        holdings_path=str(ROOT / "data/public/holdings.parquet"),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
    )


@pytest.fixture(scope="module")
def desk(engine):
    return Desk(engine)


def test_a_failed_lookup_across_tabs_leads_to_an_offer():
    out = assist.inspect_sheets(
        {"Portfolio": PORTFOLIO, "Tape": TAPE}, failed_lookups=3
    )
    assert out["should_offer"] is True
    assert out["exact"] == 0
    assert out["possible"] == 2  # KnowBe4 and Foundation appear inside longer text
    assert out["no_obvious_match"] == 1  # Exabeam borrows as LogRhythm
    assert "A lookup finds 0 of 3" in out["facts"][0]


def test_lists_that_already_line_up_get_no_offer():
    same = [
        ["Company", "Owner"],
        ["KnowBe4", "x"],
        ["Foundation", "y"],
        ["Exabeam", "z"],
    ]
    assert assist.inspect_sheets({"A": PORTFOLIO, "B": same})["should_offer"] is False


def test_a_single_list_gets_no_offer():
    assert assist.inspect_sheets({"Portfolio": PORTFOLIO})["should_offer"] is False


def test_owner_columns_are_not_read_as_company_names():
    assert assist.name_columns(PORTFOLIO) == [(0, "Company")]


def test_list_from_sheet_carries_owner_and_sector():
    assert assist.list_from_sheet(PORTFOLIO)[0] == {
        "name": "KnowBe4",
        "sponsor": "Vista",
        "sector": "Security",
    }


def test_read_workbook_keeps_every_tab(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as w:
        pd.DataFrame(PORTFOLIO).to_excel(w, sheet_name="P", index=False, header=False)
        pd.DataFrame(TAPE).to_excel(w, sheet_name="T", index=False, header=False)
    book = assist.read_workbook(path.read_bytes(), "book.xlsx")
    assert list(book) == ["P", "T"]
    assert book["P"][1][0] == "KnowBe4"


def test_read_workbook_refuses_other_file_types():
    with pytest.raises(ValueError):
        assist.read_workbook(b"x", "notes.txt")


def test_how_to_reconcile_states_the_limits_and_the_counterfactual():
    out = assist.how_to_reconcile(PROFILE, n_names=5, has_context=True)
    assert "5 names" in out["answer"]
    assert "#N/A" in out["why_not_a_lookup"]
    assert any("Banks" in x for x in out["cannot_do"])
    assert out["next_tool"] == "reconcile_list"


def test_how_to_reconcile_says_to_keep_the_ai_off_for_confidential_lists():
    assert "off" in assist.how_to_reconcile(PROFILE, confidential=True)["privacy"]


def test_reconcile_list_returns_a_source_for_every_loan(engine):
    out = assist.reconcile_list(engine, [{"name": "KnowBe4"}])
    row = out["rows"][0]
    assert row["flag"] == "Flagged"
    assert row["listed_as"] == "KnowBe4 Inc."
    assert row["loans"]
    assert all(
        x["filing_url"].startswith("https://www.sec.gov/") and x["filing_row"]
        for x in row["loans"]
    )


def test_reconcile_list_finds_a_company_that_borrows_under_another_name(engine):
    row = assist.reconcile_list(engine, [{"name": "Exabeam"}])["rows"][0]
    assert row["listed_as"] == "LogRhythm Inc."


def test_unclear_matches_are_held_for_a_person(engine):
    row = assist.reconcile_list(engine, [{"name": "Apex Group"}])["rows"][0]
    assert any(x["listed_as"] == "Apex Bidco Limited" for x in row["to_confirm"])


def test_an_unknown_company_has_no_numbers(engine):
    row = assist.reconcile_list(engine, [{"name": "Not A Real Company Xyzzy"}])["rows"][
        0
    ]
    assert row["result"] == "No public lender found"
    assert row["value_pct"] is None and row["loans"] == []


def test_reconcile_list_refuses_an_oversized_list(engine):
    with pytest.raises(ValueError):
        assist.reconcile_list(engine, [{"name": "x"}] * (assist.MAX_NAMES + 1))


def test_reconcile_list_logs_counts_and_never_names(engine):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(telemetry.JsonFormatter())
    root = logging.getLogger("erm")
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        assist.reconcile_list(engine, [{"name": "KnowBe4"}], source="test")
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)
    lines = [json.loads(x) for x in stream.getvalue().splitlines()]
    assert any(x["event"] == "run_finished" for x in lines)
    assert len({x["request_id"] for x in lines}) == 1
    assert "KnowBe4" not in stream.getvalue()


# --- Agent tools -------------------------------------------------------------------------------------


def test_mcp_inspect_sheets_takes_rows_or_a_file(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as w:
        pd.DataFrame(PORTFOLIO).to_excel(w, sheet_name="P", index=False, header=False)
        pd.DataFrame(TAPE).to_excel(w, sheet_name="T", index=False, header=False)
    assert mcp_server.inspect_sheets(path=str(path))["should_offer"] is True
    assert mcp_server.inspect_sheets(sheets={"P": PORTFOLIO, "T": TAPE})["should_offer"]


def test_mcp_inspect_sheets_needs_exactly_one_input():
    with pytest.raises(ValueError):
        mcp_server.inspect_sheets()


def test_mcp_how_to_reconcile():
    assert mcp_server.how_to_reconcile(n_names=3)["next_tool"] == "reconcile_list"


def test_mcp_reconcile_list_and_enrich_spreadsheet(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_engine", engine)
    assert (
        mcp_server.reconcile_list([{"name": "KnowBe4"}])["rows"][0]["flag"] == "Flagged"
    )
    source = tmp_path / "list.csv"
    source.write_text("Company,Owner\nKnowBe4,Vista\n")
    out = mcp_server.enrich_spreadsheet(str(source), "Company", sponsor_column="Owner")
    written = pd.read_excel(out["written_to"], sheet_name=None)
    assert out["rows"] == 1 and written["Your list"].loc[0, "Flag"] == "Flagged"
    assert written["All loans"].Filing.notna().all()
    assert source.read_text().startswith("Company,Owner")  # the original is untouched


def test_mcp_enrich_spreadsheet_refuses_other_files(tmp_path):
    with pytest.raises(ValueError):
        mcp_server.enrich_spreadsheet(str(tmp_path / "x.txt"), "Company")


# --- Assistant ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("my XLOOKUP gives #N/A", "check"),
        ("why don't these match", "check"),
        ("how do I reconcile these companies?", "how"),
        ("reconcile this list", "run"),
        ("what's for lunch", "other"),
    ],
)
def test_local_route(message, intent):
    assert assistant.route(message) == intent


class FakeBlock:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeUsage:
    input_tokens = 1
    output_tokens = 1


class FakeClient:
    """Answers with a tool call first, then with text, the way the API does."""

    def __init__(self, tool_name, tool_input):
        self.calls = []
        self.turns = [
            FakeBlock(
                stop_reason="tool_use",
                model="m",
                usage=FakeUsage,
                content=[
                    FakeBlock(type="tool_use", id="1", name=tool_name, input=tool_input)
                ],
            ),
            FakeBlock(
                stop_reason="end_turn",
                model="m",
                usage=FakeUsage,
                content=[FakeBlock(type="text", text="Done.")],
            ),
        ]
        self.beta = FakeBlock(messages=FakeBlock(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.turns[len(self.calls) - 1]


def test_claude_turn_runs_the_tool_and_returns_its_words(desk):
    client = FakeClient("reconcile_list", {"names": ["KnowBe4"]})
    ctx = {
        "sheets": {"Portfolio": PORTFOLIO},
        "list_rows": assist.list_from_sheet(PORTFOLIO),
        "reconcile": desk._reconcile,
    }
    reply = assistant.claude_reply(client, "reconcile these", [], ctx)
    assert reply == {
        "text": "Done.",
        "tools_used": ["reconcile_list"],
        "mode": "claude",
    }
    assert ctx["reconciled"]["rows"][0]["listed_as"] == "KnowBe4 Inc."
    sent = client.calls[1]["messages"][-1]["content"][0]
    assert sent["tool_use_id"] == "1" and "KnowBe4" in sent["content"]


def test_an_empty_names_list_means_the_open_sheet(desk):
    ctx = {
        "sheets": {"Portfolio": PORTFOLIO},
        "list_rows": assist.list_from_sheet(PORTFOLIO)[:1],
        "reconcile": desk._reconcile,
    }
    assistant.run_tool("reconcile_list", {"names": []}, ctx)
    assert [r["name"] for r in ctx["reconciled"]["rows"]] == ["KnowBe4"]


def test_an_empty_names_list_with_no_company_column_is_refused():
    with pytest.raises(ValueError):
        assistant.run_tool("reconcile_list", {"names": []}, {"list_rows": []})


def test_an_unknown_tool_is_refused():
    with pytest.raises(ValueError):
        assistant.run_tool("delete_everything", {}, {})


# --- Desk actions ------------------------------------------------------------------------------------


def test_demo_workbook_lookup_fails_and_every_row_has_a_filing(engine):
    book = demo_workbook(engine.holdings)
    assert len(book["Portfolio"]) == 6
    assert all(
        row[4].startswith("https://www.sec.gov/") for row in book["Lender tape"][1:]
    )
    out = assist.inspect_sheets(book, failed_lookups=5)
    assert out["should_offer"] and out["exact"] == 0


def test_desk_stays_local_unless_claude_is_turned_on(desk):
    book = desk.workbook({})["sheets"]
    reply = desk.ask(
        {"message": "how do I reconcile these?", "sheets": book, "use_claude": True}
    )
    assert reply["mode"] == "local"  # no client on this desk, so nothing can leave


def test_desk_answer_overrides_and_is_saved(desk):
    row = desk.answer(
        {"name": "Apex Group", "mention_key": "apex bidco", "same": False}
    )
    assert all(x["mention_key"] != "apex bidco" for x in row["to_confirm"])
    again = desk.reconcile({"sheets": {}, "names": ["Apex Group"]})["rows"][0]
    assert all(x["mention_key"] != "apex bidco" for x in again["to_confirm"])


def test_desk_export_is_a_real_workbook_with_sources(desk):
    book = {"Portfolio": PORTFOLIO}
    data = desk.export({"sheets": book, "sheet": "Portfolio"})
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert list(sheets) == ["Your list", "All loans"]
    assert sheets["All loans"].Filing.notna().all()
