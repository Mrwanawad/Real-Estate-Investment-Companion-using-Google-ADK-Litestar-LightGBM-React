from decimal import Decimal as D

import pytest

from reic.modules.financing.domain.comparison import compare_financing
from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.installments import InstallmentPlanSpec
from reic.modules.financing.domain.mortgage import MortgageSpec

PRICE = D("1000000")


def _plan(**kw: object) -> InstallmentPlanSpec:
    base: dict[str, object] = {
        "price_egp": PRICE,
        "down_payment_pct": D("0.1"),
        "years": 1,
        "frequency": "annual",
    }
    base.update(kw)
    return InstallmentPlanSpec(**base)  # type: ignore[arg-type]


def test_cash_vs_plan_reference_numbers() -> None:
    result = compare_financing(
        PRICE, D("0.20"), D("0.05"), installment_plans=[("1y plan", _plan())]
    )
    cash, plan = result.options
    # cash 5% off = 950,000 at month 0
    assert (cash.upfront, cash.total_nominal, cash.present_value) == (
        D("950000.00"),
        D("950000.00"),
        D("950000.00"),
    )
    assert cash.effective_cost_vs_cash == D("0.00")
    assert (cash.max_monthly_outflow, cash.avg_monthly_outflow) == (D("0.00"), D("0.00"))
    # plan: 100,000 now + 900,000 at month 12; PV at 20% = 100,000 + 750,000
    assert plan.upfront == D("100000.00")
    assert plan.total_nominal == D("1000000.00")
    assert plan.present_value == D("850000.00")
    assert plan.effective_cost_vs_cash == D("-100000.00")
    assert plan.max_monthly_outflow == D("900000.00")
    assert plan.avg_monthly_outflow == D("75000.00")  # 900,000 / 12
    assert plan.horizon_months == 12
    assert result.cheapest_label == "1y plan"
    assert [o.is_cheapest for o in result.options] == [False, True]
    codes = [n["code"] for n in result.notes]
    assert codes == ["cheapest_by_pv", "discount_rate_is_input", "cash_discount_applied"]
    assert result.assumptions["cash_price_egp"] == "950000.00"
    assert result.assumptions["discount_rate_monthly"] == "0.015309"


def test_cash_cheapest_when_no_discount_rate_advantage() -> None:
    result = compare_financing(PRICE, D("0"), D("0"), installment_plans=[("plan", _plan())])
    assert result.cheapest_label == "Cash"  # tie on PV, cash listed first wins
    assert [o.effective_cost_vs_cash for o in result.options] == [D("0.00"), D("0.00")]


def test_mortgage_and_maintenance_notes() -> None:
    result = compare_financing(
        PRICE,
        D("0.20"),
        installment_plans=[("plan", _plan(maintenance_pct=D("0.05")))],
        mortgages=[
            ("subsidised", MortgageSpec(PRICE, D("0.2"), D("0.08"), 10)),
            ("market", MortgageSpec(PRICE, D("0.2"), D("0.25"), 10)),
        ],
    )
    sub = next(o for o in result.options if o.label == "subsidised")
    mkt = next(o for o in result.options if o.label == "market")
    assert sub.kind == "mortgage" and sub.upfront == D("200000.00")
    assert sub.total_nominal < mkt.total_nominal
    assert sub.present_value < mkt.present_value
    assert sub.max_monthly_outflow == sub.avg_monthly_outflow or sub.max_monthly_outflow > 0
    codes = [n["code"] for n in result.notes]
    assert "installment_totals_include_maintenance" in codes
    assert "mortgage_excludes_fees_and_insurance" in codes
    assert "cash_discount_applied" not in codes
    assert sum(o.is_cheapest for o in result.options) == 1


def test_comparison_validation() -> None:
    plan = _plan()
    with pytest.raises(FinancingValidationError, match="unique"):
        compare_financing(PRICE, D("0.2"), installment_plans=[("Cash", plan)])
    with pytest.raises(FinancingValidationError, match="unique"):
        compare_financing(PRICE, D("0.2"), installment_plans=[("a", plan), ("a", plan)])
    with pytest.raises(FinancingValidationError, match="non-empty"):
        compare_financing(PRICE, D("0.2"), installment_plans=[(" ", plan)])
    with pytest.raises(FinancingValidationError, match="compared price_egp"):
        compare_financing(D("900000"), D("0.2"), installment_plans=[("a", plan)])
    with pytest.raises(FinancingValidationError, match="discount_rate_pct"):
        compare_financing(PRICE, D("20"))
    with pytest.raises(FinancingValidationError, match="cash_discount_pct"):
        compare_financing(PRICE, D("0.2"), D("1.5"))
    with pytest.raises(FinancingValidationError, match="price_egp"):
        compare_financing(D("0"), D("0.2"))
