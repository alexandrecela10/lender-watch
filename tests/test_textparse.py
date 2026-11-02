from erm.textparse import (
    borrowers_in,
    core,
    find_mention,
    is_funded_debt,
    lien_of,
    maturity_of,
    name_pattern,
    norm,
)


def mention(raw, name):
    return find_mention(raw, name_pattern(core(name)))


def test_core_keeps_single_letters_that_are_part_of_the_name():
    assert core("Point C") == "point c"
    assert core("Model N") == "model n"


def test_core_strips_trailing_legal_words_only():
    assert core("Apex Group") == "apex"
    assert core("Anaplan, Inc.") == "anaplan"
    assert core("The Group Company LLC") == "group company llc"  # all legal words: keep the name
    assert core("L.L.C. Foods L.L.C.") == "llc foods"


def test_norm_collapses_llc():
    assert norm("Acme, L.L.C.") == "acme llc"


def test_basis_point_is_not_a_hit_for_point_c():
    assert mention("Current Coupon 9.33% Basis Point Spread Above Index", "Point C") is None


def test_right_words_reveal_a_different_company():
    m = mention("Investments Diversified Consumer Services Apex Service Partners, LLC First Lien", "Apex Group")
    assert m.right == ("service", "partners")
    assert m.left == ()


def test_left_words_reveal_a_different_company():
    assert mention("Investments Components Wheel Pros, LLC Investment Common Equity", "PROS").left == ("wheel",)
    assert mention("Structured Credit Investment | Silver Point CLO 1 Ltd | x", "Point C") is None


def test_sector_words_do_not_count_as_name_words():
    m = mention("Debt Investments Software Anaplan, Inc. Investment First Lien Debt", "Anaplan")
    assert m.left == ()
    assert m.right == ()
    assert m.has_legal_form


def test_trade_name_in_brackets():
    m = mention("Delta TopCo, Inc. (dba Infoblox, Inc.) | First lien senior secured loan", "Infoblox")
    assert m.trade_name
    assert m.left == ()


def test_pipe_format_and_tranche_suffix():
    m = mention("KnowBe4 | Senior secured", "KnowBe4")
    assert m.key == "knowbe4"
    m = mention("Azul Systems, Inc. | Senior secured 1 | Non-Affiliated Issuer", "Azul")
    assert m.right == ("systems",)


def test_apostrophes_and_spacing():
    assert mention("Together Womens Health, LLC | Revolver", "Together Women's Health") is not None


def test_comma_without_legal_form_ends_the_name():
    m = mention("Kings Buyer, LLC, Environmental & Facilities Services, First Lien Revolver", "Kings")
    assert m.right == ("buyer",)


def test_borrowers_in_trims_sector_words():
    assert borrowers_in("Debt Investments Software Anaplan Solutions, Inc. Investment First Lien") == [
        "Anaplan Solutions Inc."
    ]


def test_lien_and_maturity():
    assert lien_of("KnowBe4 Inc. | Systems Software | First Lien Term Loan") == "first lien"
    assert lien_of("Proofpoint, Inc. | Second lien senior secured loan 1") == "second lien"
    assert maturity_of("Maturity Date 7/23/2032") == "2032-07"
    assert maturity_of("Due 11/09/2029") == "2029-11"
    assert maturity_of("whatever", "2030-06-03") == "2030-06"
    assert maturity_of("no date") is None


def test_funded_debt_filter():
    assert is_funded_debt("KnowBe4 | Senior secured")
    assert not is_funded_debt("Acumatica Holdings, Inc. | First Lien - Undrawn")
    assert not is_funded_debt("QAD, Inc. | Common stock")
    assert not is_funded_debt("Riskonnect Parent, LLC | Preferred stock 1")


def test_name_variants_and_compact():
    from erm.retrieve import compact_hit, name_variants

    assert name_variants("First Eagle Investments") == ["first eagle investments", "first eagle"]
    assert name_variants("Model N") == ["model n"]
    assert name_variants("Apex Service Partners") == ["apex service partners", "apex service"]
    assert compact_hit("AlertMedia", "Alert Media, Inc.")
    assert not compact_hit("ASG", "A S G Inc")
