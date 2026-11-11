"""Property tests: hand-rolled random loops with a fixed seed (no extra dependency)."""

import random
from decimal import Decimal as D

import pytest

from reic.modules.financing.domain.installments import (
    FREQUENCY_MONTHS,
    InstallmentPlanSpec,
    build_installment_schedule,
)
from reic.modules.financing.domain.mortgage import MortgageSpec, build_mortgage_schedule
from reic.modules.financing.domain.valuation import irr, pv

SEED = 20261109
CASES = 200


def _pct(rng: random.Random, low: float = 0.0, high: float = 1.0) -> D:
    return D(str(round(rng.uniform(low, high), 4)))


def _random_plan(rng: random.Random) -> InstallmentPlanSpec:
    years = rng.randint(1, 12)
    down = _pct(rng, 0, 0.5)
    return InstallmentPlanSpec(
        price_egp=D(str(round(rng.uniform(100_000, 20_000_000), 2))),
        down_payment_pct=down,
        years=years,
        frequency=rng.choice(list(FREQUENCY_MONTHS)),  # type: ignore[arg-type]
        delivery_payment_pct=_pct(rng, 0, float(1 - down)),
        delivery_month=rng.randint(0, years * 12),
        maintenance_pct=_pct(rng, 0, 0.1),
        annual_escalation_pct=rng.choice([D(0), _pct(rng, 0, 0.3)]),
    )


def test_installment_schedule_sums_exactly() -> None:
    rng = random.Random(SEED)
    for _ in range(CASES):
        spec = _random_plan(rng)
        schedule = build_installment_schedule(spec)
        price = spec.price_egp.quantize(D("0.01"))
        maintenance = (price * spec.maintenance_pct).quantize(D("0.01"))
        total = sum(p.amount for p in schedule.payments)
        assert total == schedule.total_nominal == price + maintenance
        assert sum(schedule.totals_by_kind.values()) == total
        assert all(p.amount >= 0 for p in schedule.payments)
        months = [p.month for p in schedule.payments]
        assert months == sorted(months)
        assert all(p.amount.as_tuple().exponent == -2 for p in schedule.payments)


def test_mortgage_balance_ends_at_zero_and_totals_tie() -> None:
    rng = random.Random(SEED + 1)
    for _ in range(CASES):
        spec = MortgageSpec(
            price_egp=D(str(round(rng.uniform(100_000, 20_000_000), 2))),
            down_payment_pct=_pct(rng, 0, 0.6),
            annual_rate_pct=rng.choice([D(0), _pct(rng, 0, 0.35)]),
            years=rng.randint(1, 30),
        )
        schedule = build_mortgage_schedule(spec)
        assert schedule.rows[-1].balance == D("0.00")
        assert all(r.balance >= 0 for r in schedule.rows)
        assert sum(r.principal for r in schedule.rows) == schedule.loan_amount
        assert schedule.total_paid == schedule.loan_amount + schedule.total_interest
        assert schedule.total_cost == schedule.down_payment + schedule.total_paid
        assert all(r.payment == r.interest + r.principal for r in schedule.rows)


def test_pv_of_zero_interest_plan_at_zero_discount_equals_nominal() -> None:
    rng = random.Random(SEED + 2)
    for _ in range(CASES):
        schedule = build_installment_schedule(_random_plan(rng))
        assert pv(D("0"), schedule.flows_by_month()) == schedule.total_nominal


def test_pv_never_exceeds_nominal_for_positive_rates() -> None:
    rng = random.Random(SEED + 3)
    for _ in range(50):
        schedule = build_installment_schedule(_random_plan(rng))
        assert pv(_pct(rng, 0.01, 0.4), schedule.flows_by_month()) <= schedule.total_nominal


@pytest.mark.parametrize("rate", ["0.05", "0.12", "0.18", "0.27"])
def test_irr_of_loan_equals_monthly_rate(rate: str) -> None:
    rng = random.Random(SEED + int(D(rate) * 100))
    for _ in range(10):
        spec = MortgageSpec(
            price_egp=D(str(round(rng.uniform(500_000, 10_000_000), 2))),
            down_payment_pct=_pct(rng, 0, 0.3),
            annual_rate_pct=D(rate),
            years=rng.randint(3, 25),
        )
        schedule = build_mortgage_schedule(spec)
        result = irr([schedule.loan_amount, *(-r.payment for r in schedule.rows)])
        assert result is not None
        assert abs(result - D(rate) / 12) <= D("0.000001")
