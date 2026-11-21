"""Letter reader and confirmations (spec section 4; checks 13, 14 and 20). A stand-in replaces the model."""

import io
import json
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from erm import letters, semantic, telemetry
from erm.prototype_store import EventStore
from eval import letters as letters_eval

LETTER = """# Synthetic Fund 1: letter to investors

20 May 2026

Synthetic letter, written by code for a test.

We marked down Synthetic Company 01 to 40.0% of cost as of 10 May 2026, reflecting weaker results.

Thank you for your continued support.
"""


def model_reply(events):
    usage = NS(
        input_tokens=500,
        output_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return NS(
        parsed_output=letters.Events(events=[letters.Event(**e) for e in events]),
        stop_reason="end_turn",
        model="claude-opus-5-5",
        usage=usage,
    )


class FakeClient:
    def __init__(self, events):
        self.events = events
        self.beta = NS(messages=NS(parse=self.parse))

    def parse(self, **kw):
        assert (
            kw["betas"] == ["server-side-fallback-2026-07-01"]
            and kw["fallbacks"] == "default"
        )
        return model_reply(self.events)


GOOD = {
    "company": "Synthetic Company 01",
    "type": "write_down",
    "size_pct_cost": 40.0,
    "effective": "2026-05-10",
    "quote": "We marked down Synthetic Company 01 to 40.0% of cost as of 10 May 2026, reflecting weaker results.",
}


def test_received_comes_from_the_letter_not_the_model():
    out = letters.read_letter(LETTER, FakeClient([GOOD]))
    assert out["received"] == "2026-05-20"
    assert out["kept"][0]["received"] == "2026-05-20"


def test_a_quote_not_in_the_letter_is_dropped():
    made_up = {**GOOD, "quote": "Synthetic Company 01 was written down to zero."}
    out = letters.read_letter(LETTER, FakeClient([GOOD, made_up]))
    assert len(out["kept"]) == 1 and out["dropped"] == 1


def test_quote_matching_ignores_spacing_and_curly_quotes():
    assert letters.quote_in("We  marked down Synthetic Company 01", LETTER)
    assert letters.quote_in("the manager’s view", "the manager's view")


def test_reader_is_off_by_default(monkeypatch):
    from erm import mcp_server

    monkeypatch.delenv("LW_PROTOTYPE_AI", raising=False)
    tool = mcp_server.mcp._tool_manager.get_tool("read_letter").fn
    assert tool("01") == {"error": letters.OFF}


@pytest.fixture
def proto(tmp_path):
    store = EventStore(tmp_path / "p.sqlite")
    p = semantic.Prototype(writedowns=store.confirmed_writedowns)
    p.store = store
    return p


def gap(p, quarter="2026-06-30", company="I01"):
    return p.get_measure("manager_lender_gap", [company], as_of=quarter)["rows"][0][
        "value"
    ]


def test_only_a_confirmed_write_down_changes_a_measure(proto):
    before = gap(proto)
    event = {**GOOD, "company_id": "I01", "received": "2026-06-01"}
    [proposed] = proto.store.propose("t", [event])
    assert gap(proto) == before  # proposed, not confirmed
    proto.store.decide(proposed["event_id"], False)
    assert gap(proto) == before  # rejected
    proto.store.decide(proposed["event_id"], True)
    lender = proto.get_measure("lender_value", ["I01"])["rows"][0]["value"]
    assert gap(proto) == pytest.approx(40.0 - lender)
    # Received after the March quarter-end, so March is unchanged.
    march = semantic.Prototype().get_measure(
        "manager_lender_gap", ["I01"], as_of="2026-03-31"
    )["rows"][0]["value"]
    assert gap(proto, "2026-03-31") == march


def test_a_write_down_the_manager_already_reported_counts_once(proto):
    before = gap(proto)
    # Received before the June manager value was reported (2026-05-15), so that value already includes it.
    [p] = proto.store.propose(
        "t", [{**GOOD, "company_id": "I01", "received": "2026-05-01"}]
    )
    proto.store.decide(p["event_id"], True)
    assert gap(proto) == before


def test_scoring_matches_on_company_type_date_and_size():
    events = letters_eval.truth()
    perfect = {
        letter: [
            {
                "company_id": t.company_id,
                "type": t.type,
                "effective": t.effective,
                "size_pct_cost": None
                if t.size_pct_cost == ""
                else float(t.size_pct_cost) + 0.3,
            }
            for t in group.itertuples()
        ]
        for letter, group in events.groupby("letter")
    }
    s = letters_eval.score(perfect, events)
    assert (s["found"], s["wrong"]) == (len(events), 0)
    first = events.iloc[0]
    shifted = {**perfect}
    shifted[first.letter] = [dict(p) for p in perfect[first.letter]]
    shifted[first.letter][0]["effective"] = "2020-01-01"
    s = letters_eval.score(shifted, events)
    assert (s["found"], s["wrong"]) == (len(events) - 1, 1)
    assert s["fields_right"]["effective"] == len(events) - 1


def test_logs_hold_no_letter_text_quote_or_company_name(proto):
    stream = io.StringIO()
    telemetry.configure(stream=stream)
    try:
        letters.read_letter(LETTER, FakeClient([GOOD]))
        proto.get_measure("manager_lender_gap", ["Synthetic Company 01", "KnowBe4"])
    finally:
        telemetry.configure()
    text = stream.getvalue()
    assert text and all(json.loads(x) for x in text.splitlines())
    for secret in ["Synthetic Company", "KnowBe4", "marked down", "weaker results"]:
        assert secret not in text, secret


def test_truth_file_has_both_event_types():
    events = pd.read_csv(semantic.SYN / "events.csv", keep_default_na=False)
    assert set(events.type) == {"write_down", "covenant_breach"}
