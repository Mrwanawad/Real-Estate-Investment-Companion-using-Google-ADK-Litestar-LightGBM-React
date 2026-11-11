from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from reic.modules.inventory.adapters.outbound import tables as t
from reic.modules.inventory.domain.models import (
    Area,
    Developer,
    PaymentPlan,
    Project,
    Unit,
    UnitDetail,
    UnitQuery,
)


def _area(row: Row[Any]) -> Area:
    return Area(
        id=row.area_id,
        name_en=row.area_name_en,
        name_ar=row.area_name_ar,
        type=row.area_type,
        base_price_per_m2_2015=row.base_price_per_m2_2015,
        liquidity_tier=row.liquidity_tier,
        gross_rental_yield_base=row.gross_rental_yield_base,
    )


class SqlUnitStore:
    """UnitStore over SQLAlchemy async sessions (Postgres)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _detail_query() -> Select[Any]:
        return (
            select(
                *t.units.c,
                t.projects.c.name_en.label("project_name_en"),
                t.projects.c.name_ar.label("project_name_ar"),
                t.projects.c.area_id,
                t.projects.c.developer_id,
                t.projects.c.launch_year,
                t.projects.c.delivery_year.label("project_delivery_year"),
                t.projects.c.amenities,
                t.areas.c.name_en.label("area_name_en"),
                t.areas.c.name_ar.label("area_name_ar"),
                t.areas.c.type.label("area_type"),
                t.areas.c.base_price_per_m2_2015,
                t.areas.c.liquidity_tier,
                t.areas.c.gross_rental_yield_base,
                t.developers.c.name_en.label("developer_name_en"),
                t.developers.c.tier.label("developer_tier"),
                t.developers.c.on_time_delivery_rate,
            )
            .select_from(
                t.units.join(t.projects, t.units.c.project_id == t.projects.c.id)
                .join(t.areas, t.projects.c.area_id == t.areas.c.id)
                .join(t.developers, t.projects.c.developer_id == t.developers.c.id)
            )
            .order_by(t.units.c.price_egp, t.units.c.code)
        )

    async def search(self, query: UnitQuery, limit: int) -> list[UnitDetail]:
        stmt = self._detail_query()
        if query.budget_max_egp is not None:
            stmt = stmt.where(t.units.c.price_egp <= query.budget_max_egp)
        if query.area_ids:
            stmt = stmt.where(t.projects.c.area_id.in_(query.area_ids))
        if query.types:
            stmt = stmt.where(t.units.c.type.in_(query.types))
        if query.bedrooms_min is not None:
            stmt = stmt.where(t.units.c.bedrooms >= query.bedrooms_min)
        if query.delivery_by_year is not None:
            stmt = stmt.where(t.units.c.delivery_year <= query.delivery_by_year)
        if query.status is not None:
            stmt = stmt.where(t.units.c.status == query.status)
        rows = (await self._session.execute(stmt.limit(limit))).all()
        return await self._hydrate(rows)

    async def get_by_code(self, code: str) -> UnitDetail | None:
        rows = (
            await self._session.execute(self._detail_query().where(t.units.c.code == code))
        ).all()
        details = await self._hydrate(rows)
        return details[0] if details else None

    async def list_areas(self) -> list[Area]:
        rows = (await self._session.execute(select(t.areas).order_by(t.areas.c.id))).all()
        return [
            Area(
                id=r.id,
                name_en=r.name_en,
                name_ar=r.name_ar,
                type=r.type,
                base_price_per_m2_2015=r.base_price_per_m2_2015,
                liquidity_tier=r.liquidity_tier,
                gross_rental_yield_base=r.gross_rental_yield_base,
            )
            for r in rows
        ]

    async def _hydrate(self, rows: Sequence[Row[Any]]) -> list[UnitDetail]:
        if not rows:
            return []
        project_ids = sorted({r.project_id for r in rows})
        plan_rows = (
            await self._session.execute(
                select(t.payment_plans)
                .where(t.payment_plans.c.project_id.in_(project_ids))
                .order_by(t.payment_plans.c.id)
            )
        ).all()
        plans: dict[str, list[PaymentPlan]] = defaultdict(list)
        for p in plan_rows:
            plans[p.project_id].append(
                PaymentPlan(
                    id=p.id,
                    project_id=p.project_id,
                    name=p.name,
                    down_payment_pct=p.down_payment_pct,
                    years=p.years,
                    frequency=p.frequency,
                    delivery_payment_pct=p.delivery_payment_pct,
                    maintenance_pct=p.maintenance_pct,
                    cash_discount_pct=p.cash_discount_pct,
                )
            )
        details = []
        for r in rows:
            project = Project(
                id=r.project_id,
                name_en=r.project_name_en,
                name_ar=r.project_name_ar,
                area_id=r.area_id,
                developer_id=r.developer_id,
                launch_year=r.launch_year,
                delivery_year=r.project_delivery_year,
                amenities=tuple(a for a in r.amenities.split("|") if a),
            )
            unit = Unit(
                code=r.code,
                project_id=r.project_id,
                type=cast(Any, r.type),
                bedrooms=r.bedrooms,
                bua_m2=r.bua_m2,
                garden_m2=r.garden_m2,
                floor=r.floor,
                finishing=cast(Any, r.finishing),
                delivery_year=r.delivery_year,
                status=cast(Any, r.status),
                price_egp=r.price_egp,
                view=r.view,
            )
            developer = Developer(
                id=r.developer_id,
                name_en=r.developer_name_en,
                tier=cast(Any, r.developer_tier),
                on_time_delivery_rate=r.on_time_delivery_rate,
            )
            details.append(
                UnitDetail(
                    unit=unit,
                    project=project,
                    area=_area(r),
                    developer=developer,
                    plans=tuple(plans[r.project_id]),
                )
            )
        return details
