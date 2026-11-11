from reic.modules.companion.domain.grounding import extract_numbers, ungrounded_numbers
from reic.modules.companion.domain.profile import BuyerProfile, missing_for


def test_profile_merge_ignores_invalid_and_accumulates_areas() -> None:
    p = BuyerProfile().merge(goal="flip", budget_egp=-5, areas=["New Cairo"], horizon_years=50)
    assert p.goal is None and p.budget_egp is None and p.horizon_years is None
    p = p.merge(goal="rent", budget_egp="3000000", areas=["Madinaty", "New Cairo"])
    assert p.goal == "rent" and p.budget_egp == 3_000_000
    assert p.areas == ("New Cairo", "Madinaty")


def test_missing_for_caps_questions() -> None:
    assert missing_for(BuyerProfile(), "projection") == ["goal", "budget_egp"]
    assert missing_for(BuyerProfile(phone="010"), "handoff") == []
    assert missing_for(BuyerProfile(), "handoff") == ["phone_or_email"]


def test_extract_numbers_handles_units_and_arabic_digits() -> None:
    assert extract_numbers("4.85M EGP and 12%") == [(4_850_000.0, False), (12.0, True)]
    assert extract_numbers("٣ مليون") == [(3_000_000.0, False)]


def test_grounding_flags_only_invented_material_numbers() -> None:
    sources = [{"price_egp": "4800000.00", "irr": {"p50": 0.121}, "year": 2029}]
    assert ungrounded_numbers("Price 4.8M, IRR about 12%, delivery 2029, 3 bedrooms", sources) == []
    assert ungrounded_numbers("It will be worth 9,000,000 EGP", sources) == [9_000_000.0]


def test_grounding_reads_numbers_inside_labels() -> None:
    sources = [{"cheapest_label": "5% down / 9 years quarterly"}]
    assert ungrounded_numbers("Cheapest: 5% down over 9 years", sources) == []
