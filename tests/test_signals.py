import pandas as pd

from erm.signals import facts_for, flags_for, usable

Q1, Q2 = "2026-03-31", "2026-06-30"


def row(lender, period, text, principal, fv, lien="first lien", maturity=None, pik=None):
    return dict(lender=lender, period=period, raw_text=text, principal=principal, fair_value=fv, lien=lien,
                maturity=maturity, pik_rate=pik, pct_par=fv / principal * 100, excluded_reason="",
                inlineurl=f"https://sec.gov/{lender}", filed="2026-08-11")


def test_fall_is_found_loan_by_loan_not_hidden_by_an_average():
    rows = pd.DataFrame([
        row("A", Q1, "KnowBe4 | Senior secured", 100, 89.7), row("A", Q2, "KnowBe4 | Senior secured", 100, 78.5),
        row("A", Q1, "KnowBe4 | Other", 900, 900), row("A", Q2, "KnowBe4 | Other", 900, 900),
    ])
    facts = facts_for(rows, Q2, Q1)
    assert facts[0].pct_par == 78.5
    assert facts[0].previous_pct_par == 89.7
    flags = flags_for(facts)
    assert flags.dropped and flags.below_90
    assert flags.level == "worth_a_look"  # 10% of the debt fell; the whole is still near par
    assert "89.7% to 78.5%" in flags.summary


def test_most_debt_below_90_is_flagged():
    rows = pd.DataFrame([
        row("A", Q1, "KnowBe4 | a", 100, 89.7), row("A", Q2, "KnowBe4 | a", 100, 78.5),
        row("B", Q1, "KnowBe4 | b", 100, 88.8), row("B", Q2, "KnowBe4 | b", 100, 77.5),
    ])
    flags = flags_for(facts_for(rows, Q2, Q1))
    assert flags.level == "flagged"
    assert flags.weighted_pct_par == 78.0
    assert flags.weighted_change == -11.2


def test_one_small_position_cannot_flag_a_company():
    # A large position near par and one $8k position well below it.
    rows = pd.DataFrame([row("A", Q2, "Vessco | a", 10_000_000, 10_000_000), row("B", Q2, "Vessco | b", 8_000, 5_000)])
    flags = flags_for(facts_for(rows, Q2, None))
    assert flags.level == "worth_a_look"
    assert "$8k" in flags.summary


def test_company_change_needs_half_the_debt_paired():
    rows = pd.DataFrame([
        row("A", Q1, "Acme | a", 100, 100), row("A", Q2, "Acme | a", 100, 80),
        row("B", Q2, "Acme | b", 900, 900),
    ])
    assert flags_for(facts_for(rows, Q2, Q1)).weighted_change is None


def test_unchanged_loan_cannot_be_paired_with_a_different_loan():
    # Oaktree on KnowBe4: 1.501M stays at par; the 1.494M row must not borrow the 1.501M row's prior value.
    rows = pd.DataFrame([
        row("O", Q1, "KnowBe4 Inc., First Lien Term Loan", 1501, 1505),
        row("O", Q1, "KnowBe4 Inc. | Systems Software | First Lien Term Loan", 4787, 4292),
        row("O", Q2, "KnowBe4 Inc., First Lien Term Loan", 1501, 1505),
        row("O", Q2, "KnowBe4 Inc. | Systems Software | First Lien Term Loan", 1494, 1173),
    ])
    facts = {f.principal: f for f in facts_for(rows, Q2, Q1)}
    assert facts[1501].change == 0
    assert facts[1494].previous_pct_par is None  # size changed by more than 25%: not claimed as the same position


def test_rate_change_in_text_still_pairs_the_loan():
    rows = pd.DataFrame([
        row("B", Q1, "Acme Inc. First Lien Spread 5.00% Rate 9.1% Maturity 6/1/2030", 100, 98),
        row("B", Q2, "Acme Inc. First Lien Spread 5.00% Rate 8.7% Maturity 6/1/2030", 99, 90),
    ])
    assert facts_for(rows, Q2, Q1)[0].change == round(90 / 99 * 100 - 98, 1)


def test_gap_needs_the_same_lien_and_maturity():
    different = pd.DataFrame([
        row("K", Q2, "x", 100, 71.5, maturity=None), row("N", Q2, "y", 100, 99, maturity="2030-01"),
    ])
    assert not flags_for(facts_for(different, Q2, None)).lender_gap
    same = pd.DataFrame([
        row("K", Q2, "x", 100, 84, maturity="2030-01"), row("N", Q2, "y", 100, 96, maturity="2030-01"),
    ])
    flags = flags_for(facts_for(same, Q2, None))
    assert flags.lender_gap
    assert "96.0%" in flags.summary


def test_duplicate_rows_count_once():
    rows = pd.DataFrame([row("A", Q2, "Acme | a", 100, 90), row("A", Q2, "Acme | b", 100, 90)])
    assert len(usable(rows)) == 1


def test_no_flags_is_stated_plainly():
    flags = flags_for(facts_for(pd.DataFrame([row("A", Q2, "Acme", 100, 99)]), Q2, None))
    assert not flags.any
    assert flags.level == "none"
    assert "no large fall" in flags.summary


def test_every_fact_carries_its_source():
    f = facts_for(pd.DataFrame([row("A", Q2, "Acme", 100, 99)]), Q2, None)[0]
    assert f.filing_url and f.filing_row
