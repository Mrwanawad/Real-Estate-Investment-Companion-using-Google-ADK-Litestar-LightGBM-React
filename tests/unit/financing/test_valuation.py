"""PV / NPV / IRR against numpy-financial and independently computed references."""

import random
from decimal import Decimal as D

import numpy as np
import numpy_financial as npf
import pytest

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.installments import (
    InstallmentPlanSpec,
    build_installment_schedule,
)
from reic.modules.financing.domain.mortgage import MortgageSpec, build_mortgage_schedule
from reic.modules.financing.domain.valuation import (
    annualize,
    irr,
    monthly_rate,
    npv,
    npv_periodic,
    pv,
)

# ---- (a) PMT: mortgage payment vs numpy-financial, 12 parametrized cases

PMT_CASES = [
    ("1000000", "0.12", 10),
    ("2500000", "0.08", 15),
    ("750000", "0.18", 5),
    ("4200000", "0.225", 20),
    ("300000", "0.05", 30),
    ("1800000", "0.15", 8),
    ("999999.99", "0.0925", 12),
    ("5000000", "0.27", 7),
    ("640000", "0.01", 25),
    ("1234567.89", "0.135", 18),
    ("90000", "0.3", 3),
    ("3300000", "0.0", 10),
]


@pytest.mark.parametrize(("price", "rate", "years"), PMT_CASES)
def test_mortgage_matches_numpy_financial(price: str, rate: str, years: int) -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D(price), D("0"), D(rate), years))
    monthly, months, loan = float(rate) / 12, years * 12, float(price)
    expected = -npf.pmt(monthly, months, loan) if monthly else loan / months
    assert abs(float(schedule.monthly_payment) - expected) <= 0.005 + 1e-9
    interest = -npf.ipmt(monthly, np.arange(1, months + 1), months, loan).sum() if monthly else 0.0
    # Rounding the payment to the piastre shifts the balance by up to 0.005 per month, compounded
    # at the loan rate and settled by the final payment: bound ~ 0.005 * FV annuity factor.
    fv_factor = ((1 + monthly) ** months - 1) / monthly if monthly else months
    assert abs(float(schedule.total_interest) - interest) <= 0.005 * (fv_factor + months)
    assert schedule.rows[-1].balance == D("0.00")


# ---- (a) NPV and IRR vs numpy-financial on random flows (fixed seed), 12 cases each


def _random_flows(seed: int) -> list[D]:
    rng = random.Random(seed)
    n = rng.randint(3, 60)
    flows = [D(str(round(rng.uniform(-50000, 90000), 2))) for _ in range(n)]
    flows[0] = -abs(flows[0]) - D("100000")
    flows[-1] = abs(flows[-1]) + D("400000")
    return flows


@pytest.mark.parametrize("seed", range(12))
def test_npv_matches_numpy_financial(seed: int) -> None:
    flows = _random_flows(seed)
    annual = D(str(round(random.Random(seed).uniform(0.01, 0.4), 4)))
    expected = npf.npv((1 + float(annual)) ** (1 / 12) - 1, [float(f) for f in flows])
    assert abs(float(npv(annual, flows)) - expected) <= 0.0051


@pytest.mark.parametrize("seed", range(12))
def test_irr_matches_numpy_financial(seed: int) -> None:
    flows = _random_flows(seed)
    expected = float(npf.irr([float(f) for f in flows]))
    result = irr(flows)
    assert result is not None
    assert abs(float(result) - expected) <= 5e-7 + 1e-12
    assert result == result.quantize(D("0.000001"))


# ---- (b) textbook references


def test_textbook_npv_and_irr() -> None:
    flows = [D(-100), D(39), D(59), D(55), D(20)]
    # exact value 573890/14641 = 39.19745...
    assert npv_periodic(0.10, flows) == D("39.20")
    assert irr(flows) == D("0.280948")


def test_pv_of_single_flow_at_annual_rate() -> None:
    # 1,000,000 due in 12 months at 20% effective annual: 1,000,000 / 1.2 = 833,333.33
    assert pv(D("0.20"), {12: D("1000000")}) == D("833333.33")
    assert abs(monthly_rate(D("0.20")) - 0.015309470499731193) < 1e-15
    assert pv(D("0.20"), {0: D("500"), 12: D("600"), 6: D("0")}) == D("1000.00")


def test_zero_rate_is_exact_sum() -> None:
    flows = {0: D("0.10"), 1: D("0.20"), 5: D("0.30")}
    assert pv(D("0"), flows) == D("0.60")
    assert npv(D("0"), [D("1.01"), D("2.02")]) == D("3.03")


def test_irr_none_cases_and_annualized() -> None:
    assert irr([D(1), D(2), D(3)]) is None
    assert irr([D(-1), D(-2)]) is None
    assert irr([D(0), D(0)]) is None
    assert irr([D(1), D(-3), D(3)]) is None  # sign changes but numpy-financial finds no root
    assert irr([D(-100), D(121)]) == D("0.210000")
    assert irr([D(-100), D(121)], annualized=True) == annualize(D("0.21"))
    assert annualize(D("0.01")) == D("0.126825")  # 1.01**12 - 1


def test_irr_of_loan_cash_flows_is_monthly_rate() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("1000000"), D("0"), D("0.12"), years=10))
    flows = [schedule.loan_amount, *(-r.payment for r in schedule.rows)]
    assert irr(flows) == D("0.010000")
    assert irr(flows, annualized=True) == D("0.126825")


def test_installment_plan_pv_reference() -> None:
    # 100,000 down + 900,000 after 12 months; 20% discount: 100,000 + 900,000/1.2 = 850,000
    schedule = build_installment_schedule(
        InstallmentPlanSpec(D("1000000"), D("0.1"), years=1, frequency="annual")
    )
    assert pv(D("0.20"), schedule.flows_by_month()) == D("850000.00")


@pytest.mark.parametrize(
    "call",
    [
        lambda: npv(D("0.1"), []),
        lambda: pv(D("0.1"), {}),
        lambda: pv(D("0.1"), {-1: D(5)}),
        lambda: monthly_rate(D("-1")),
        lambda: monthly_rate(D("NaN")),
    ],
)
def test_valuation_validation(call) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FinancingValidationError):
        call()
