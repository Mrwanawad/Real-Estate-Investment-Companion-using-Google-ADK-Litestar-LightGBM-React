"""Use cases. Results are JSON-ready dicts: money and rates are strings to keep exact digits."""

from decimal import Decimal
from typing import Any

from reic.modules.financing.application.dto import (
    CompareFinancingInput,
    InstallmentScheduleInput,
    InstallmentTerms,
    MortgageScheduleInput,
    MortgageTerms,
)
from reic.modules.financing.domain.comparison import compare_financing
from reic.modules.financing.domain.installments import (
    InstallmentPlanSpec,
    build_installment_schedule,
)
from reic.modules.financing.domain.mortgage import MortgageSpec, build_mortgage_schedule


def _installment_spec(
    terms: InstallmentTerms, price: Decimal, cash_discount: Decimal
) -> InstallmentPlanSpec:
    return InstallmentPlanSpec(
        price_egp=price,
        down_payment_pct=terms.down_payment_pct,
        years=terms.years,
        frequency=terms.frequency,
        delivery_payment_pct=terms.delivery_payment_pct,
        delivery_month=terms.delivery_month,
        maintenance_pct=terms.maintenance_pct,
        annual_escalation_pct=terms.annual_escalation_pct,
        cash_discount_pct=cash_discount,
    )


def _mortgage_spec(terms: MortgageTerms, price: Decimal) -> MortgageSpec:
    return MortgageSpec(
        price_egp=price,
        down_payment_pct=terms.down_payment_pct,
        annual_rate_pct=terms.annual_rate_pct,
        years=terms.years,
        rate_type=terms.rate_type,
    )


class BuildInstallmentSchedule:
    def execute(self, data: InstallmentScheduleInput) -> dict[str, Any]:
        spec = _installment_spec(data, data.price_egp, data.cash_discount_pct)
        schedule = build_installment_schedule(spec)
        return {
            "price_egp": str(schedule.spec.price_egp),
            "total_nominal": str(schedule.total_nominal),
            "upfront": str(schedule.upfront),
            "cash_price_egp": str(schedule.cash_price_egp),
            "installment_count": schedule.installment_count,
            "totals_by_kind": {k: str(v) for k, v in schedule.totals_by_kind.items()},
            "payments": [
                {"index": p.index, "month": p.month, "kind": p.kind, "amount": str(p.amount)}
                for p in schedule.payments
            ],
        }


class BuildMortgageSchedule:
    def execute(self, data: MortgageScheduleInput) -> dict[str, Any]:
        schedule = build_mortgage_schedule(_mortgage_spec(data, data.price_egp))
        return {
            "loan_amount": str(schedule.loan_amount),
            "down_payment": str(schedule.down_payment),
            "monthly_payment": str(schedule.monthly_payment),
            "total_interest": str(schedule.total_interest),
            "total_paid": str(schedule.total_paid),
            "total_cost": str(schedule.total_cost),
            "rows": [
                {
                    "month": r.month,
                    "payment": str(r.payment),
                    "interest": str(r.interest),
                    "principal": str(r.principal),
                    "balance": str(r.balance),
                }
                for r in schedule.rows
            ],
        }


class CompareFinancingOptions:
    def execute(self, data: CompareFinancingInput) -> dict[str, Any]:
        result = compare_financing(
            price_egp=data.price_egp,
            discount_rate_pct=data.discount_rate_pct,
            cash_discount_pct=data.cash_discount_pct,
            installment_plans=[
                (p.label, _installment_spec(p, data.price_egp, data.cash_discount_pct))
                for p in data.installment_plans
            ],
            mortgages=[(m.label, _mortgage_spec(m, data.price_egp)) for m in data.mortgages],
        )
        return {
            "cheapest_label": result.cheapest_label,
            "options": [
                {
                    "label": o.label,
                    "kind": o.kind,
                    "upfront": str(o.upfront),
                    "max_monthly_outflow": str(o.max_monthly_outflow),
                    "avg_monthly_outflow": str(o.avg_monthly_outflow),
                    "horizon_months": o.horizon_months,
                    "total_nominal": str(o.total_nominal),
                    "present_value": str(o.present_value),
                    "effective_cost_vs_cash": str(o.effective_cost_vs_cash),
                    "is_cheapest": o.is_cheapest,
                }
                for o in result.options
            ],
            "assumptions": result.assumptions,
            "notes": list(result.notes),
        }
