from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Literal

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.installments import (
    InstallmentPlanSpec,
    build_installment_schedule,
)
from reic.modules.financing.domain.money import (
    ZERO,
    q2,
    q6,
    require_fraction,
    require_positive,
)
from reic.modules.financing.domain.mortgage import MortgageSpec, build_mortgage_schedule
from reic.modules.financing.domain.valuation import monthly_rate, pv

OptionKind = Literal["cash", "installment", "mortgage"]


@dataclass(frozen=True)
class FinancingOption:
    label: str
    kind: OptionKind
    upfront: Decimal
    max_monthly_outflow: Decimal
    avg_monthly_outflow: Decimal
    horizon_months: int
    total_nominal: Decimal
    present_value: Decimal
    effective_cost_vs_cash: Decimal
    is_cheapest: bool = False


@dataclass(frozen=True)
class CompareFinancing:
    options: tuple[FinancingOption, ...]
    cheapest_label: str
    assumptions: dict[str, str]
    notes: tuple[dict[str, Any], ...]


def _option(
    label: str,
    kind: OptionKind,
    flows: Mapping[int, Decimal],
    discount_rate: Decimal,
    cash_pv: Decimal,
) -> FinancingOption:
    total = sum(flows.values(), ZERO)
    upfront = flows.get(0, ZERO)
    horizon = max(flows)
    later = [amount for month, amount in flows.items() if month > 0]
    present = pv(discount_rate, flows)
    return FinancingOption(
        label=label,
        kind=kind,
        upfront=upfront,
        max_monthly_outflow=max(later, default=ZERO),
        avg_monthly_outflow=q2((total - upfront) / horizon) if horizon > 0 else ZERO,
        horizon_months=horizon,
        total_nominal=total,
        present_value=present,
        effective_cost_vs_cash=present - cash_pv,
    )


def compare_financing(
    price_egp: Decimal,
    discount_rate_pct: Decimal,
    cash_discount_pct: Decimal = Decimal(0),
    installment_plans: Sequence[tuple[str, InstallmentPlanSpec]] = (),
    mortgages: Sequence[tuple[str, MortgageSpec]] = (),
) -> CompareFinancing:
    """Compare paying cash (with discount), installment plans and mortgages on a like-for-like
    basis. ``discount_rate_pct`` is an annual fraction supplied by the caller (for example the
    deposit rate an investor could otherwise earn); it is an input, never a built-in claim."""
    require_positive("price_egp", price_egp)
    require_fraction("discount_rate_pct", discount_rate_pct)
    require_fraction("cash_discount_pct", cash_discount_pct)
    labelled = [*installment_plans, *mortgages]
    labels = ["Cash", *(label for label, _ in labelled)]
    if any(not label.strip() for label in labels) or len(set(labels)) != len(labels):
        raise FinancingValidationError("option labels must be non-empty and unique")
    for label, spec in labelled:
        if q2(spec.price_egp) != q2(price_egp):
            raise FinancingValidationError(f"option {label!r} must use the compared price_egp")

    cash_price = q2(price_egp * (1 - cash_discount_pct))
    cash_pv = pv(discount_rate_pct, {0: cash_price})
    options = [_option("Cash", "cash", {0: cash_price}, discount_rate_pct, cash_pv)]
    for label, plan in installment_plans:
        schedule = build_installment_schedule(plan)
        options.append(
            _option(label, "installment", schedule.flows_by_month(), discount_rate_pct, cash_pv)
        )
    for label, mortgage in mortgages:
        schedule_m = build_mortgage_schedule(mortgage)
        options.append(
            _option(label, "mortgage", schedule_m.flows_by_month(), discount_rate_pct, cash_pv)
        )

    cheapest = min(options, key=lambda o: o.present_value)
    options = [replace(o, is_cheapest=o is cheapest) for o in options]

    notes: list[dict[str, Any]] = [
        {"code": "cheapest_by_pv", "label": cheapest.label, "pv_egp": str(cheapest.present_value)},
        {"code": "discount_rate_is_input", "annual_rate": str(discount_rate_pct)},
    ]
    if cash_discount_pct > 0:
        notes.append({"code": "cash_discount_applied", "pct": str(cash_discount_pct)})
    if any(plan.maintenance_pct > 0 for _, plan in installment_plans):
        notes.append({"code": "installment_totals_include_maintenance"})
    if mortgages:
        notes.append({"code": "mortgage_excludes_fees_and_insurance"})

    assumptions = {
        "price_egp": str(q2(price_egp)),
        "cash_price_egp": str(cash_price),
        "cash_discount_pct": str(cash_discount_pct),
        "discount_rate_annual": str(discount_rate_pct),
        "discount_rate_monthly": str(q6(Decimal(repr(monthly_rate(discount_rate_pct))))),
        "discounting": "monthly flows, (1+r)^(1/12)-1, month 0 undiscounted",
        "upfront": "total paid at month 0 (signing)",
        "max_monthly_outflow": "largest total due in any single month after month 0",
        "avg_monthly_outflow": "(total nominal - upfront) / last payment month",
        "effective_cost_vs_cash": "present value minus present value of the cash option",
    }
    return CompareFinancing(
        options=tuple(options),
        cheapest_label=cheapest.label,
        assumptions=assumptions,
        notes=tuple(notes),
    )
