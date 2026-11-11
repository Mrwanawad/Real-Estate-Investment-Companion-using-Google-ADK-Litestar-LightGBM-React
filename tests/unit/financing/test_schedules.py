"""Installment and mortgage schedules: hand-worked references and validation (see
financing_reference.md for how each number was derived)."""

from decimal import Decimal as D

import numpy_financial as npf
import pytest

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.installments import (
    InstallmentPlanSpec,
    build_installment_schedule,
)
from reic.modules.financing.domain.mortgage import MortgageSpec, build_mortgage_schedule

# ---------------------------------------------------------------- installments


def test_quarterly_zero_interest_reference() -> None:
    spec = InstallmentPlanSpec(D("3000000"), D("0.10"), years=7, frequency="quarterly")
    schedule = build_installment_schedule(spec)
    down, *installments = schedule.payments
    assert (down.month, down.kind, down.amount) == (0, "down", D("300000.00"))
    assert len(installments) == 28 == schedule.installment_count
    assert [p.amount for p in installments[:27]] == [D("96428.57")] * 27
    last = installments[-1]
    assert (last.month, last.kind, last.amount) == (84, "final", D("96428.61"))
    assert schedule.total_nominal == D("3000000.00")
    assert schedule.upfront == D("300000.00")
    assert [p.index for p in schedule.payments] == list(range(29))
    assert schedule.cash_price_egp == D("3000000.00")


def test_delivery_and_maintenance_reference() -> None:
    spec = InstallmentPlanSpec(
        D("2000000"),
        D("0.10"),
        years=5,
        frequency="annual",
        delivery_payment_pct=D("0.20"),
        delivery_month=36,
        maintenance_pct=D("0.05"),
        cash_discount_pct=D("0.05"),
    )
    schedule = build_installment_schedule(spec)
    by_month = [(p.month, p.kind, p.amount) for p in schedule.payments]
    assert by_month == [
        (0, "down", D("200000.00")),
        (12, "installment", D("280000.00")),
        (24, "installment", D("280000.00")),
        (36, "installment", D("280000.00")),
        (36, "delivery", D("400000.00")),
        (36, "maintenance", D("100000.00")),
        (48, "installment", D("280000.00")),
        (60, "final", D("280000.00")),
    ]
    assert schedule.total_nominal == D("2100000.00")  # price + maintenance
    assert schedule.totals_by_kind["installment"] == D("1400000.00")
    assert schedule.cash_price_egp == D("1900000.00")
    assert schedule.flows_by_month()[36] == D("780000.00")


def test_escalating_installments_reference() -> None:
    spec = InstallmentPlanSpec(
        D("1000000"), D("0.10"), years=3, frequency="annual", annual_escalation_pct=D("0.10")
    )
    amounts = [p.amount for p in build_installment_schedule(spec).payments[1:]]
    assert amounts == [D("271903.32"), D("299093.66"), D("329003.02")]
    assert sum(amounts) == D("900000.00")


def test_full_down_payment_has_no_installments() -> None:
    schedule = build_installment_schedule(InstallmentPlanSpec(D("500000"), D("1"), years=2))
    assert [p.kind for p in schedule.payments] == ["down"]
    assert schedule.installment_count == 0


def test_single_installment_is_final_and_monthly_count() -> None:
    one = build_installment_schedule(
        InstallmentPlanSpec(D("100"), D("0"), years=1, frequency="annual")
    )
    assert [(p.kind, p.amount) for p in one.payments] == [("final", D("100.00"))]
    monthly = build_installment_schedule(
        InstallmentPlanSpec(D("120000"), D("0"), years=1, frequency="monthly")
    )
    assert monthly.installment_count == 12
    assert {p.amount for p in monthly.payments} == {D("10000.00")}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"down_payment_pct": D("1.5")}, "down_payment_pct must be between 0 and 1"),
        ({"down_payment_pct": D("-0.1")}, "down_payment_pct must be between 0 and 1"),
        ({"price_egp": D("0")}, "price_egp must be greater than 0"),
        ({"price_egp": D("NaN")}, "price_egp must be a finite number"),
        ({"price_egp": 1000.0}, "price_egp must be a finite number"),
        ({"years": 0}, "years must be a whole number"),
        ({"years": True}, "years must be a whole number"),
        ({"frequency": "weekly"}, "frequency must be one of"),
        (
            {"down_payment_pct": D("0.7"), "delivery_payment_pct": D("0.4")},
            "must not exceed 1",
        ),
        ({"delivery_month": 99}, "delivery_month must be a whole month between 0 and 60"),
        ({"delivery_month": -1}, "delivery_month must be a whole month"),
        ({"delivery_month": True}, "delivery_month must be a whole month"),
        ({"maintenance_pct": D("2")}, "maintenance_pct must be between"),
        ({"cash_discount_pct": D("1.01")}, "cash_discount_pct must be between"),
    ],
)
def test_installment_validation(overrides: dict[str, object], message: str) -> None:
    kwargs: dict[str, object] = {
        "price_egp": D("1000000"),
        "down_payment_pct": D("0.1"),
        "years": 5,
    }
    kwargs.update(overrides)
    with pytest.raises(FinancingValidationError, match=message):
        InstallmentPlanSpec(**kwargs)  # type: ignore[arg-type]


# ------------------------------------------------------------------- mortgage


def test_mortgage_reference_one_million_twelve_percent_ten_years() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("1000000"), D("0"), D("0.12"), years=10))
    assert schedule.monthly_payment == D("14347.09")
    assert len(schedule.rows) == 120
    first = schedule.rows[0]
    assert (first.interest, first.principal, first.balance) == (
        D("10000.00"),
        D("4347.09"),
        D("995652.91"),
    )
    assert schedule.rows[-1].balance == D("0.00")
    assert schedule.total_paid == schedule.loan_amount + schedule.total_interest
    assert D("721650") < schedule.total_interest < D("721652")  # 120 * 14347.09 - 1,000,000


def test_mortgage_small_loan_full_amortisation_reference() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("100000"), D("0"), D("0.12"), years=1))
    assert schedule.monthly_payment == D("8884.88")
    rows = {r.month: r for r in schedule.rows}
    assert (rows[1].interest, rows[1].principal, rows[1].balance) == (
        D("1000.00"),
        D("7884.88"),
        D("92115.12"),
    )
    assert (rows[2].interest, rows[2].balance) == (D("921.15"), D("84151.39"))
    assert (rows[12].payment, rows[12].interest, rows[12].balance) == (
        D("8884.85"),
        D("87.97"),
        D("0.00"),
    )
    assert schedule.total_interest == D("6618.53")
    assert schedule.total_paid == D("106618.53")


def test_mortgage_with_down_payment_and_flows() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("1000000"), D("0.2"), D("0.09"), years=5))
    assert (schedule.down_payment, schedule.loan_amount) == (D("200000.00"), D("800000.00"))
    assert schedule.total_cost == schedule.down_payment + schedule.total_paid
    assert schedule.flows_by_month()[0] == D("200000.00")
    expected = -npf.pmt(0.09 / 12, 60, 800000)
    assert abs(float(schedule.monthly_payment) - expected) <= 0.005


def test_zero_rate_mortgage() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("120000"), D("0"), D("0"), years=1))
    assert {r.payment for r in schedule.rows} == {D("10000.00")}
    assert schedule.total_interest == D("0.00")
    uneven = build_mortgage_schedule(MortgageSpec(D("100"), D("0"), D("0"), years=1))
    assert uneven.monthly_payment == D("8.33")
    assert uneven.rows[-1].payment == D("8.37")  # 100 - 11 * 8.33
    assert sum(r.payment for r in uneven.rows) == D("100.00")


def test_mortgage_fully_paid_in_cash_has_no_rows() -> None:
    schedule = build_mortgage_schedule(MortgageSpec(D("500000"), D("1"), D("0.1"), years=3))
    assert schedule.rows == ()
    assert schedule.monthly_payment == D("0.00")
    assert schedule.total_cost == D("500000.00")
    assert schedule.flows_by_month() == {0: D("500000.00")}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"down_payment_pct": D("2")}, "down_payment_pct must be between 0 and 1"),
        ({"annual_rate_pct": D("12")}, "annual_rate_pct must be between 0 and 1"),
        ({"years": 51}, "years must be a whole number"),
        ({"rate_type": "floating"}, "rate_type must be 'fixed'"),
        ({"price_egp": D("-5")}, "price_egp must be greater than 0"),
    ],
)
def test_mortgage_validation(overrides: dict[str, object], message: str) -> None:
    kwargs: dict[str, object] = {
        "price_egp": D("1000000"),
        "down_payment_pct": D("0.1"),
        "annual_rate_pct": D("0.1"),
        "years": 10,
    }
    kwargs.update(overrides)
    with pytest.raises(FinancingValidationError, match=message):
        MortgageSpec(**kwargs)  # type: ignore[arg-type]
