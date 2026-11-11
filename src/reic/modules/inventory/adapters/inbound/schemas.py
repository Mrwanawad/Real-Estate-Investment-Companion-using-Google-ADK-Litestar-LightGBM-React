from pydantic import BaseModel, Field

from reic.modules.inventory.domain.models import (
    Area,
    Goal,
    PaymentPlan,
    UnitDetail,
    UnitQuery,
)
from reic.modules.inventory.domain.scoring import PlanFeasibility, ScoredUnit


class SearchRequest(UnitQuery):
    """UnitQuery plus free-text areas (ids, English or Arabic names, aliases) and a limit."""

    areas: tuple[str, ...] = ()
    limit: int = Field(default=50, ge=1, le=200)


class ShortlistRequest(SearchRequest):
    goal: Goal = "live"
    limit: int = Field(default=5, ge=1, le=20)


class AreaOut(BaseModel):
    id: str
    name_en: str
    name_ar: str
    type: str
    liquidity_tier: int
    gross_rental_yield_base: float

    @classmethod
    def from_domain(cls, area: Area) -> "AreaOut":
        return cls(
            id=area.id,
            name_en=area.name_en,
            name_ar=area.name_ar,
            type=area.type,
            liquidity_tier=area.liquidity_tier,
            gross_rental_yield_base=area.gross_rental_yield_base,
        )


class PaymentPlanOut(BaseModel):
    id: str
    name: str
    down_payment_pct: float
    years: int
    frequency: str
    delivery_payment_pct: float
    maintenance_pct: float
    cash_discount_pct: float

    @classmethod
    def from_domain(cls, plan: PaymentPlan) -> "PaymentPlanOut":
        return cls(
            id=plan.id,
            name=plan.name,
            down_payment_pct=plan.down_payment_pct,
            years=plan.years,
            frequency=plan.frequency,
            delivery_payment_pct=plan.delivery_payment_pct,
            maintenance_pct=plan.maintenance_pct,
            cash_discount_pct=plan.cash_discount_pct,
        )


class UnitOut(BaseModel):
    code: str
    type: str
    bedrooms: int
    bua_m2: float
    garden_m2: float
    floor: int
    finishing: str
    delivery_year: int
    status: str
    price_egp: int
    view: str
    project_id: str
    project_name_en: str
    project_name_ar: str
    amenities: list[str]
    area: AreaOut
    developer_id: str
    developer_name_en: str
    developer_tier: str
    developer_on_time_delivery_rate: float
    plans: list[PaymentPlanOut]

    @classmethod
    def from_domain(cls, detail: UnitDetail) -> "UnitOut":
        u = detail.unit
        return cls(
            code=u.code,
            type=u.type,
            bedrooms=u.bedrooms,
            bua_m2=u.bua_m2,
            garden_m2=u.garden_m2,
            floor=u.floor,
            finishing=u.finishing,
            delivery_year=u.delivery_year,
            status=u.status,
            price_egp=u.price_egp,
            view=u.view,
            project_id=detail.project.id,
            project_name_en=detail.project.name_en,
            project_name_ar=detail.project.name_ar,
            amenities=list(detail.project.amenities),
            area=AreaOut.from_domain(detail.area),
            developer_id=detail.developer.id,
            developer_name_en=detail.developer.name_en,
            developer_tier=detail.developer.tier,
            developer_on_time_delivery_rate=detail.developer.on_time_delivery_rate,
            plans=[PaymentPlanOut.from_domain(p) for p in detail.plans],
        )


class PlanFeasibilityOut(BaseModel):
    plan_id: str
    plan_name: str
    down_payment_egp: float
    delivery_payment_egp: float
    monthly_installment_egp: float
    note: str = "Coarse level-installment estimate; use the financing calculator for exact numbers."

    @classmethod
    def from_domain(cls, plan: PlanFeasibility) -> "PlanFeasibilityOut":
        return cls(
            plan_id=plan.plan_id,
            plan_name=plan.plan_name,
            down_payment_egp=round(plan.down_payment_egp),
            delivery_payment_egp=round(plan.delivery_payment_egp),
            monthly_installment_egp=round(plan.monthly_installment_egp),
        )


class ShortlistItemOut(BaseModel):
    unit: UnitOut
    score: float
    components: dict[str, float]
    best_plan: PlanFeasibilityOut

    @classmethod
    def from_domain(cls, scored: ScoredUnit) -> "ShortlistItemOut":
        return cls(
            unit=UnitOut.from_domain(scored.detail),
            score=scored.score,
            components=scored.components,
            best_plan=PlanFeasibilityOut.from_domain(scored.best_plan),
        )
