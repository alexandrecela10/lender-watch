"""Change explainer (spec section 5; checks 17 and 18). A stand-in replaces the model."""

from types import SimpleNamespace as NS

import pytest

from erm import explain, semantic


@pytest.fixture(scope="module")
def proto():
    return semantic.Prototype()


@pytest.mark.parametrize("measure", ["cost_in_flagged", "share_cost_flagged"])
def test_parts_sum_to_the_total_over_the_whole_portfolio(proto, measure):
    out = explain.explain(proto, measure, list(proto.portfolio.companies.company_id))
    assert out["sum_check"]
    unrounded = sum(x["amount"] for x in out["parts"] if x["label"] != "rounding")
    assert unrounded == pytest.approx(out["total"])
    assert out["sentence_from"] == "template"


def test_parts_sum_for_every_invented_company_on_measure_6(proto):
    invented = proto.portfolio.companies.query("kind == 'invented'").company_id
    for cid in invented:
        out = explain.explain(proto, "manager_lender_gap", [cid])
        assert out["sum_check"], cid
        if out["parts"]:
            labels = {
                x["label"].split(": ")[1]
                for x in out["parts"]
                if x["label"] != "rounding"
            }
            assert labels <= {
                "manager's value moved",
                "write-down we confirmed",
                "lenders raised their value of the debt",
                "lenders cut their value of the debt",
            }
            for x in out["parts"]:
                # The lenders' part names what lenders did, and says how it moved the gap.
                if "lenders" in x["label"]:
                    assert x["direction"] in ("narrowed the gap", "widened the gap")


def test_shown_parts_add_up_with_a_rounding_part(proto):
    out = explain.explain(
        proto, "cost_in_flagged", list(proto.portfolio.companies.company_id)
    )
    shown = sum(explain.shown(x["amount"], "usd") for x in out["parts"])
    assert shown == explain.shown(out["total"], "usd")


def test_measure_6_is_explained_one_company_at_a_time(proto):
    with pytest.raises(ValueError, match="one company at a time"):
        explain.explain(proto, "manager_lender_gap", ["I01", "I02"])
    with pytest.raises(ValueError, match="no explainer"):
        explain.explain(proto, "lender_value", ["KnowBe4"])


class FakeClient:
    def __init__(self, text):
        self.text = text
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        sent = kw["messages"][0]["content"]
        # Labels may hold company names with digits; no amount is ever sent.
        assert not any(x in sent for x in ("$", "%", "points", "rose", "fell"))
        return NS(
            content=[NS(type="text", text=self.text)],
            stop_reason="end_turn",
            model="claude-opus-5-5",
        )


@pytest.mark.parametrize(
    "words",
    [
        "Our cost in flagged companies rose by $17 million.",
        "The total went up, mostly because of {part_1.label}.",
        "{total.direction} by {total.amount}, led by {part_99.label}.",
        "It {total.direction} by {total.amount} {part_1.amount",
    ],
    ids=[
        "a number",
        "a direction word",
        "a part that doesn't exist",
        "a broken placeholder",
    ],
)
def test_a_sentence_with_anything_outside_a_placeholder_is_rejected(proto, words):
    ids = list(proto.portfolio.companies.company_id)
    out = explain.explain(proto, "cost_in_flagged", ids, client=FakeClient(words))
    assert out["sentence_from"] == "template"


def test_a_clean_sentence_is_filled_by_code(proto):
    ids = list(proto.portfolio.companies.company_id)
    words = "Our cost in flagged companies {total.direction} by {total.amount}, mostly from {part_1.label} ({part_1.amount})."
    out = explain.explain(proto, "cost_in_flagged", ids, client=FakeClient(words))
    assert out["sentence_from"] == "model"
    assert (
        out["total_shown"] in out["sentence"]
        and out["parts"][0]["shown"] in out["sentence"]
    )
    assert "{" not in out["sentence"]
