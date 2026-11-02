import pandas as pd

from erm.connectors.bdc import enrich
from erm.api import lender_data_label
from erm.store import Store


def out(status, facts=(), excluded=None):
    return {"resolution": {"status": status}, "facts": list(facts), "excluded": excluded or {}}


def test_unclear_match_never_reads_as_no_data():
    assert lender_data_label(out("needs_review")) == "To confirm"
    assert lender_data_label(out("needs_review", [{}])) == "Found, more matches to confirm"


def test_rows_with_unusable_amounts_never_read_as_no_data():
    assert "can't be used" in lender_data_label(out("matched", excluded={"amounts don't line up": 2}))


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
    assert s.save("Orion Group", "orion services", "match", "judge").verdict == "no_match"


def test_foreign_loan_in_local_currency_is_left_out_not_read_as_a_markdown():
    # 123Dentist: principal in Canadian dollars, cost and value in US dollars. Reads about 70% of par without this rule.
    h = pd.DataFrame([dict(raw_text="123Dentist Inc 2 | First Lien", principal=55904000.0, cost=42891000.0, fair_value=39351000.0, maturity_col=None, adsh="a")])
    assert enrich(h).excluded_reason[0] == "amounts don't line up"
    near_par = h.assign(cost=55000000.0, fair_value=50000000.0)
    assert enrich(near_par).excluded_reason[0] == ""
