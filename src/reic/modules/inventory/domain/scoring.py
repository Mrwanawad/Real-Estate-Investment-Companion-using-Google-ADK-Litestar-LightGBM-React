"""Shortlist scoring: a coarse feasibility filter plus a goal-weighted fit score.

Feasibility here uses simple level installments (the remaining price after the down payment and
the delivery payment, spread evenly over the plan years). It deliberately ignores maintenance
deposits, price escalation and discounting: a precise calculator lives in the financing module.
Treat this as a first-pass filter, not as a payment quote.
"""

import math
from dataclasses import dataclass, field

from reic.modules.inventory.domain.models import Goal, PaymentPlan, UnitDetail, UnitQuery

# Weights per goal; each row sums to 1.
GOAL_WEIGHTS: dict[Goal, dict[str, float]] = {
    "live": {
        "budget_fit": 0.25,
        "affordability": 0.15,
        "delivery": 0.30,
        "rental_yield": 0.0,
        "liquidity": 0.05,
        "developer_risk": 0.25,
    },
    "rent": {
        "budget_fit": 0.15,
        "affordability": 0.15,
        "delivery": 0.15,
        "rental_yield": 0.30,
        "liquidity": 0.10,
        "developer_risk": 0.15,
    },
    "resell": {
        "budget_fit": 0.15,
        "affordability": 0.10,
        "delivery": 0.15,
        "rental_yield": 0.05,
        "liquidity": 0.35,
        "developer_risk": 0.20,
    },
}
_LIQUIDITY_SCORE = {1: 1.0, 2: 0.6, 3: 0.3}
_TIER_SCORE = {"A": 1.0, "B": 0.7, "C": 0.4}


@dataclass(frozen=True, slots=True)
class PlanFeasibility:
    plan_id: str
    plan_name: str
    down_payment_egp: float
    delivery_payment_egp: float
    monthly_installment_egp: float  # normalised to a monthly amount (quarterly / 3)
    feasible: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoredUnit:
    detail: UnitDetail
    score: float
    components: dict[str, float]
    best_plan: PlanFeasibility
    notes: tuple[str, ...] = field(default=())


class ShortlistScorer:
    def __init__(self, as_of_year: int = 2026) -> None:
        self._as_of_year = as_of_year

    def evaluate_plan(self, price_egp: int, plan: PaymentPlan, query: UnitQuery) -> PlanFeasibility:
        down = price_egp * plan.down_payment_pct
        at_delivery = price_egp * plan.delivery_payment_pct
        remaining = price_egp - down - at_delivery
        monthly = remaining / (plan.years * 12)
        reasons: list[str] = []
        available = query.down_payment_available_egp
        if available is not None and down > available:
            reasons.append(f"down payment {down:,.0f} exceeds available {available:,}")
        capacity = query.monthly_capacity_egp
        if capacity is not None and monthly > capacity:
            reasons.append(f"monthly installment {monthly:,.0f} exceeds capacity {capacity:,}")
        return PlanFeasibility(
            plan_id=plan.id,
            plan_name=plan.name,
            down_payment_egp=down,
            delivery_payment_egp=at_delivery,
            monthly_installment_egp=monthly,
            feasible=not reasons,
            reasons=tuple(reasons),
        )

    def score(self, detail: UnitDetail, query: UnitQuery, goal: Goal) -> ScoredUnit | None:
        """Score a unit, or return None when it is over budget or no plan is feasible."""
        price = detail.unit.price_egp
        budget = query.budget_max_egp
        if budget is not None and price > budget:
            return None
        evaluations = [self.evaluate_plan(price, plan, query) for plan in detail.plans]
        feasible = [e for e in evaluations if e.feasible]
        if not feasible:
            return None
        best = min(feasible, key=lambda e: (e.monthly_installment_egp, e.plan_id))

        components = {
            "budget_fit": self._budget_fit(price, budget),
            "affordability": self._affordability(best, query),
            "delivery": self._delivery(detail),
            "rental_yield": self._yield(detail),
            "liquidity": _LIQUIDITY_SCORE.get(detail.area.liquidity_tier, 0.3),
            "developer_risk": self._developer(detail),
        }
        weights = GOAL_WEIGHTS[goal]
        total = sum(weights[name] * value for name, value in components.items())
        return ScoredUnit(
            detail=detail,
            score=round(total, 4),
            components={k: round(v, 4) for k, v in components.items()},
            best_plan=best,
        )

    def rank(self, details: list[UnitDetail], query: UnitQuery, goal: Goal) -> list[ScoredUnit]:
        scored = [s for d in details if (s := self.score(d, query, goal)) is not None]
        scored.sort(key=lambda s: (-s.score, s.detail.unit.code))
        return scored

    @staticmethod
    def _budget_fit(price: int, budget: int | None) -> float:
        if budget is None:
            return 0.5
        # Using 70-100% of the budget is a full fit; much cheaper units fit proportionally less.
        return min(1.0, (price / budget) / 0.7)

    @staticmethod
    def _affordability(best: PlanFeasibility, query: UnitQuery) -> float:
        parts: list[float] = []
        if query.monthly_capacity_egp:
            parts.append(1 - best.monthly_installment_egp / query.monthly_capacity_egp)
        if query.down_payment_available_egp:
            parts.append(1 - best.down_payment_egp / query.down_payment_available_egp)
        if not parts:
            return 0.5
        return max(0.0, min(1.0, sum(parts) / len(parts)))

    def _delivery(self, detail: UnitDetail) -> float:
        years = max(0, detail.unit.delivery_year - self._as_of_year)
        return math.exp(-years / 3)

    @staticmethod
    def _yield(detail: UnitDetail) -> float:
        # Gross yield of 3% maps to 0 and 6% or more to 1.
        return max(0.0, min(1.0, (detail.area.gross_rental_yield_base - 0.03) / 0.03))

    def _developer(self, detail: UnitDetail) -> float:
        if detail.unit.delivery_year <= self._as_of_year:
            return 1.0  # already delivered: no delivery risk
        dev = detail.developer
        on_time = max(0.0, min(1.0, (dev.on_time_delivery_rate - 0.5) / 0.5))
        return 0.5 * _TIER_SCORE[dev.tier] + 0.5 * on_time
