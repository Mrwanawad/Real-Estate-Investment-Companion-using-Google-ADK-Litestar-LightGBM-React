from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, get_args

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.money import (
    ZERO,
    q2,
    require_fraction,
    require_positive,
    require_years,
)

Frequency = Literal["monthly", "quarterly", "semiannual", "annual"]
PaymentKind = Literal["down", "installment", "delivery", "maintenance", "final"]

FREQUENCY_MONTHS: dict[str, int] = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
_KIND_RANK = {"down": 0, "installment": 1, "final": 1, "delivery": 2, "maintenance": 3}


@dataclass(frozen=True)
class InstallmentPlanSpec:
    """Developer installment plan. Month 0 is signing; ``delivery_month`` is an offset in months.

    The balance after down payment and delivery payment is spread over ``years`` at the chosen
    frequency (first installment one period after signing). With ``annual_escalation_pct`` > 0
    installments grow by that fraction per plan year (payment weights (1+g)^year, still summing
    to the balance). Maintenance is charged on top of the price, at delivery.
    """

    price_egp: Decimal
    down_payment_pct: Decimal
    years: int
    frequency: Frequency = "quarterly"
    delivery_payment_pct: Decimal = Decimal(0)
    delivery_month: int = 0
    maintenance_pct: Decimal = Decimal(0)
    annual_escalation_pct: Decimal = Decimal(0)
    cash_discount_pct: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        require_positive("price_egp", self.price_egp)
        require_fraction("down_payment_pct", self.down_payment_pct)
        require_fraction("delivery_payment_pct", self.delivery_payment_pct)
        require_fraction("maintenance_pct", self.maintenance_pct)
        require_fraction("annual_escalation_pct", self.annual_escalation_pct)
        require_fraction("cash_discount_pct", self.cash_discount_pct)
        require_years("years", self.years)
        if self.frequency not in get_args(Frequency):
            raise FinancingValidationError(
                f"frequency must be one of {', '.join(get_args(Frequency))}, got {self.frequency!r}"
            )
        if self.down_payment_pct + self.delivery_payment_pct > 1:
            raise FinancingValidationError(
                "down_payment_pct + delivery_payment_pct must not exceed 1"
            )
        if (
            isinstance(self.delivery_month, bool)
            or not isinstance(self.delivery_month, int)
            or not 0 <= self.delivery_month <= self.years * 12
        ):
            raise FinancingValidationError(
                f"delivery_month must be a whole month between 0 and {self.years * 12}"
            )


@dataclass(frozen=True)
class Payment:
    index: int
    month: int
    kind: PaymentKind
    amount: Decimal


@dataclass(frozen=True)
class InstallmentSchedule:
    spec: InstallmentPlanSpec
    payments: tuple[Payment, ...]
    total_nominal: Decimal
    upfront: Decimal
    totals_by_kind: dict[str, Decimal]
    installment_count: int
    cash_price_egp: Decimal

    def flows_by_month(self) -> dict[int, Decimal]:
        flows: dict[int, Decimal] = {}
        for payment in self.payments:
            flows[payment.month] = flows.get(payment.month, ZERO) + payment.amount
        return flows


def build_installment_schedule(spec: InstallmentPlanSpec) -> InstallmentSchedule:
    price = q2(spec.price_egp)
    down = q2(price * spec.down_payment_pct)
    delivery = q2(price * spec.delivery_payment_pct)
    maintenance = q2(price * spec.maintenance_pct)
    remaining = price - down - delivery

    step = FREQUENCY_MONTHS[spec.frequency]
    count = spec.years * 12 // step
    rows: list[tuple[int, PaymentKind, Decimal]] = []
    if down > 0:
        rows.append((0, "down", down))
    if delivery > 0:
        rows.append((spec.delivery_month, "delivery", delivery))
    if maintenance > 0:
        rows.append((spec.delivery_month, "maintenance", maintenance))

    if remaining > 0:
        months = [step * i for i in range(1, count + 1)]
        weights = [(1 + spec.annual_escalation_pct) ** ((m - 1) // 12) for m in months]
        weight_total = sum(weights)
        amounts = [q2(remaining * w / weight_total) for w in weights[:-1]]
        amounts.append(remaining - sum(amounts))  # last installment absorbs rounding
        for position, (month, amount) in enumerate(zip(months, amounts, strict=True)):
            kind: PaymentKind = "final" if position == count - 1 else "installment"
            rows.append((month, kind, amount))

    rows.sort(key=lambda row: (row[0], _KIND_RANK[row[1]]))
    payments = tuple(
        Payment(index=i, month=month, kind=kind, amount=amount)
        for i, (month, kind, amount) in enumerate(rows)
    )
    totals: dict[str, Decimal] = {}
    for payment in payments:
        key = "installment" if payment.kind == "final" else payment.kind
        totals[key] = totals.get(key, ZERO) + payment.amount
    return InstallmentSchedule(
        spec=spec,
        payments=payments,
        total_nominal=sum((p.amount for p in payments), ZERO),
        upfront=sum((p.amount for p in payments if p.month == 0), ZERO),
        totals_by_kind=totals,
        installment_count=count if remaining > 0 else 0,
        cash_price_egp=q2(price * (1 - spec.cash_discount_pct)),
    )
