from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.money import (
    ZERO,
    q2,
    require_fraction,
    require_positive,
    require_years,
)


@dataclass(frozen=True)
class MortgageSpec:
    """Fixed-rate annuity mortgage. ``annual_rate_pct`` is a nominal annual fraction (0.12 =
    12 percent), applied monthly as rate/12. Subsidised vs market tiers are just different
    input rates; no rate is assumed here."""

    price_egp: Decimal
    down_payment_pct: Decimal
    annual_rate_pct: Decimal
    years: int
    rate_type: Literal["fixed"] = "fixed"

    def __post_init__(self) -> None:
        require_positive("price_egp", self.price_egp)
        require_fraction("down_payment_pct", self.down_payment_pct)
        require_fraction("annual_rate_pct", self.annual_rate_pct)
        require_years("years", self.years)
        if self.rate_type != "fixed":
            raise FinancingValidationError(f"rate_type must be 'fixed', got {self.rate_type!r}")


@dataclass(frozen=True)
class AmortizationRow:
    month: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


@dataclass(frozen=True)
class MortgageSchedule:
    spec: MortgageSpec
    loan_amount: Decimal
    down_payment: Decimal
    monthly_payment: Decimal
    rows: tuple[AmortizationRow, ...]
    total_interest: Decimal
    total_paid: Decimal  # all loan payments, excluding the down payment
    total_cost: Decimal  # down payment + all loan payments

    def flows_by_month(self) -> dict[int, Decimal]:
        flows = {0: self.down_payment} if self.down_payment > 0 else {}
        flows.update({row.month: row.payment for row in self.rows})
        return flows


def annuity_payment(loan: Decimal, monthly_rate: Decimal, months: int) -> Decimal:
    """Standard PMT: L*r / (1 - (1+r)^-n), or L/n at zero rate. Unrounded."""
    if monthly_rate == 0:
        return loan / months
    with localcontext() as ctx:
        ctx.prec = 50
        growth = (1 + monthly_rate) ** months
        return loan * monthly_rate * growth / (growth - 1)


def build_mortgage_schedule(spec: MortgageSpec) -> MortgageSchedule:
    price = q2(spec.price_egp)
    down = q2(price * spec.down_payment_pct)
    loan = price - down
    months = spec.years * 12
    rate = spec.annual_rate_pct / 12
    payment = q2(annuity_payment(loan, rate, months)) if loan > 0 else ZERO

    rows: list[AmortizationRow] = []
    balance = loan
    for month in range(1, months + 1):
        if balance <= 0:
            break
        interest = q2(balance * rate)
        if month == months:
            this_payment = balance + interest  # final payment clears the balance exactly
            principal = balance
        else:
            this_payment = payment
            principal = payment - interest
        balance -= principal
        rows.append(AmortizationRow(month, this_payment, interest, principal, balance))

    total_interest = sum((r.interest for r in rows), ZERO)
    total_paid = sum((r.payment for r in rows), ZERO)
    return MortgageSchedule(
        spec=spec,
        loan_amount=loan,
        down_payment=down,
        monthly_payment=payment,
        rows=tuple(rows),
        total_interest=total_interest,
        total_paid=total_paid,
        total_cost=down + total_paid,
    )
