"""Wiring for the companion: the backend gateway over the other modules, the engine and router.

The companion module only sees the CompanionBackend port; this file is the one place that knows
how inventory, financing, market, scenarios, knowledge and handoff fit together.
"""

import asyncio
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.companion.adapters.outbound.adk_engine import AdkEngine
from reic.modules.companion.adapters.outbound.llm import build_llm
from reic.modules.companion.application.chat import ChatService
from reic.modules.financing.application.dto import CompareFinancingInput
from reic.modules.financing.application.use_cases import CompareFinancingOptions
from reic.modules.handoff.application.service import HandoffService
from reic.modules.inventory.adapters.outbound.sql_unit_store import SqlUnitStore
from reic.modules.inventory.application.use_cases import BuildShortlist
from reic.modules.inventory.domain.errors import InventoryError
from reic.modules.inventory.domain.models import UnitDetail, UnitQuery
from reic.modules.knowledge.application.service import KnowledgeService
from reic.modules.market.application.service import MarketService
from reic.modules.reports.application.service import ReportService
from reic.modules.scenarios.application.service import ScenarioService
from reic.shared.config import Settings

AS_OF_YEAR = 2026
_COMPONENT_REASONS = {
    "budget_fit": "fits the budget",
    "affordability": "payment plan fits the monthly capacity",
    "delivery": "near delivery",
    "rental_yield": "strong rental yield for the area",
    "liquidity": "liquid resale area",
    "developer_risk": "reliable developer",
}


def _shortlist_item(scored: Any) -> dict[str, Any]:
    d: UnitDetail = scored.detail
    strongest = sorted(scored.components.items(), key=lambda kv: kv[1], reverse=True)
    reasons = [
        _COMPONENT_REASONS[k] for k, v in strongest[:3] if v >= 0.6 and k in _COMPONENT_REASONS
    ]
    reasons += list(scored.notes)
    return {
        "code": d.unit.code,
        "project_name": d.project.name_en,
        "area_name": d.area.name_en,
        "area_name_ar": d.area.name_ar,
        "type": d.unit.type,
        "bedrooms": d.unit.bedrooms,
        "bua_m2": d.unit.bua_m2,
        "price_egp": d.unit.price_egp,
        "delivery_year": d.unit.delivery_year,
        "developer_tier": d.developer.tier,
        "score": round(scored.score, 3),
        "reasons": reasons,
        "monthly_installment_egp": round(scored.best_plan.monthly_installment_egp),
        "down_payment_egp": round(scored.best_plan.down_payment_egp),
    }


def _unit_facts(d: UnitDetail) -> dict[str, Any]:
    return {
        "code": d.unit.code,
        "price_egp": d.unit.price_egp,
        "area_id": d.area.id,
        "area_name": d.area.name_en,
        "type": d.unit.type,
        "bedrooms": d.unit.bedrooms,
        "bua_m2": d.unit.bua_m2,
        "garden_m2": d.unit.garden_m2,
        "floor": d.unit.floor,
        "finishing": d.unit.finishing,
        "delivery_year": d.unit.delivery_year,
        "developer_tier": d.developer.tier,
        "developer_on_time_rate": d.developer.on_time_delivery_rate,
        "liquidity_tier": d.area.liquidity_tier,
        "plans": [
            {
                "name": p.name,
                "down_payment_pct": p.down_payment_pct,
                "years": p.years,
                "frequency": p.frequency,
                "delivery_payment_pct": p.delivery_payment_pct,
                "maintenance_pct": p.maintenance_pct,
                "cash_discount_pct": p.cash_discount_pct,
            }
            for p in d.plans
        ],
    }


class AppBackend:
    """CompanionBackend over the module services."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        market: MarketService,
        scenarios: ScenarioService,
        knowledge: KnowledgeService,
        handoff: HandoffService,
    ) -> None:
        self._sessions = session_factory
        self._settings = settings
        self._market = market
        self._scenarios = scenarios
        self._knowledge = knowledge
        self._handoff = handoff

    async def shortlist(self, criteria: dict[str, Any], goal: str, limit: int) -> dict[str, Any]:
        query = UnitQuery(
            budget_max_egp=criteria.get("budget_max_egp"),
            down_payment_available_egp=criteria.get("down_payment_available_egp"),
            monthly_capacity_egp=criteria.get("monthly_capacity_egp"),
            types=tuple(criteria.get("types") or ()),
            bedrooms_min=criteria.get("bedrooms_min"),
        )
        async with self._sessions() as session:
            try:
                scored = await BuildShortlist(SqlUnitStore(session)).execute(
                    query,
                    goal,
                    areas=criteria.get("areas") or (),
                    limit=limit,  # type: ignore[arg-type]
                )
            except InventoryError as exc:
                raise ValueError(str(exc)) from exc
        return {"units": [_shortlist_item(s) for s in scored]}

    async def unit(self, code: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            detail = await SqlUnitStore(session).get_by_code(code)
        return _unit_facts(detail) if detail else None

    async def compare_financing(self, unit: dict[str, Any]) -> dict[str, Any]:
        price = Decimal(unit["price_egp"])
        months_to_delivery = max(0, (unit["delivery_year"] - AS_OF_YEAR) * 12)
        plans = []
        for i, p in enumerate(unit["plans"], start=1):
            plans.append(
                {
                    "label": p["name"] or f"Plan {i}",
                    "down_payment_pct": Decimal(str(p["down_payment_pct"])),
                    "years": p["years"],
                    "frequency": p["frequency"],
                    "delivery_payment_pct": Decimal(str(p["delivery_payment_pct"])),
                    "delivery_month": min(months_to_delivery, p["years"] * 12),
                    "maintenance_pct": Decimal(str(p["maintenance_pct"])),
                }
            )
        labels = [p["label"] for p in plans]
        for i, p in enumerate(plans):  # labels must be unique
            if labels.count(p["label"]) > 1:
                p["label"] = f"{p['label']} #{i + 1}"
        cash_discount = max((p["cash_discount_pct"] for p in unit["plans"]), default=0.0)
        data = CompareFinancingInput(
            price_egp=price,
            discount_rate_pct=Decimal(str(self._settings.discount_rate)),
            cash_discount_pct=Decimal(str(cash_discount)),
            installment_plans=plans,  # type: ignore[arg-type]
            mortgages=[
                {  # type: ignore[list-item]
                    "label": f"Bank mortgage ({self._settings.mortgage_years}y)",
                    "down_payment_pct": Decimal("0.20"),
                    "annual_rate_pct": Decimal(str(self._settings.mortgage_rate)),
                    "years": self._settings.mortgage_years,
                }
            ],
        )
        result = CompareFinancingOptions().execute(data)
        return {"unit_code": unit["code"], "price_egp": str(price), **result}

    async def project_returns(
        self, unit: dict[str, Any], horizon_years: int, goal: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        features = {
            k: unit[k]
            for k in (
                "area_id",
                "type",
                "bedrooms",
                "bua_m2",
                "garden_m2",
                "floor",
                "finishing",
                "delivery_year",
                "developer_tier",
                "price_egp",
            )
        }
        price = float(unit["price_egp"])
        value, rent, vol = await asyncio.gather(
            self._market.unit_value(features, horizon_years),
            self._market.rent_estimate(features, price),
            self._market.annual_volatility(unit["area_id"]),
        )
        years_to_delivery = min(max(0, unit["delivery_year"] - AS_OF_YEAR), horizon_years)
        gross_yield = float(rent.get("gross_yield") or 0.0) if goal == "rent" else 0.0
        sim = self._scenarios.simulate(
            {
                "price_egp": price,
                "horizon_years": horizon_years,
                "annual_growth_mean": float(value["annual_growth"]["p50"]),
                "annual_growth_vol": min(max(float(vol), 0.05), 0.5),
                "gross_yield": min(gross_yield, 0.5),
                "goal": goal,
                "years_to_delivery": years_to_delivery,
                "inflation_mean": self._settings.inflation_mean,
            }
        )
        current = value["current"]
        risks = self._scenarios.risk_summary(
            {
                "developer_on_time_rate": unit["developer_on_time_rate"],
                "years_to_delivery": max(0, unit["delivery_year"] - AS_OF_YEAR),
                "liquidity_tier": unit["liquidity_tier"],
                "price_egp": price,
                "value_p10": min(float(current["p10"]), float(current["p50"])),
                "value_p50": float(current["p50"]),
                "prob_real_loss": float(sim["prob_real_loss"]),
            }
        )
        projection = {
            "unit_code": unit["code"],
            "price_egp": price,
            "horizon_years": horizon_years,
            "fair_value_now": current,
            "value": sim["value_at_horizon"],
            "value_path": sim["value_path"],
            "rent": {
                "monthly_p50": rent.get("monthly_rent_p50"),
                "gross_yield": rent.get("gross_yield"),
            },
            "irr": sim["irr"],
            "total_return_pct": sim["total_return_pct"],
            "prob_loss": sim["prob_loss"],
            "prob_real_loss": sim["prob_real_loss"],
            "break_even_year": sim["break_even_year"],
            "sensitivity": sim["sensitivity"],
            "models": {"value": value.get("model"), "rent": rent.get("model")},
        }
        return projection, risks

    async def search_knowledge(self, query: str, language: str) -> dict[str, Any]:
        hits = await asyncio.to_thread(self._knowledge.search, query, 4, language)
        return {
            "items": [
                {
                    "doc_id": h["doc_id"],
                    "title": h["title"],
                    "snippet": h["text"][:240],
                    "text": h["text"][:900],
                }
                for h in hits
            ]
        }

    async def create_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        return await self._handoff.create_lead(lead)


def build_chat_service(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    market: MarketService,
    scenarios: ScenarioService,
    knowledge: KnowledgeService,
    handoff: HandoffService,
    reports: ReportService,
) -> ChatService:
    def secret(value: Any) -> str | None:
        return value.get_secret_value() if value else None

    llm = build_llm(
        settings.llm_provider,
        anthropic_model=settings.anthropic_model,
        gemini_model=settings.gemini_model,
        anthropic_api_key=secret(settings.anthropic_api_key),
        gemini_api_key=secret(settings.gemini_api_key),
    )
    backend = AppBackend(session_factory, settings, market, scenarios, knowledge, handoff)
    return ChatService(
        AdkEngine(llm, stream=settings.llm_provider != "fake"),
        backend,
        reports,
        pdf_available=reports.pdf_available,
    )
