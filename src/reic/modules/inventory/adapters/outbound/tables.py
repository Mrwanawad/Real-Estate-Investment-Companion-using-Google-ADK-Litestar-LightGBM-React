"""SQLAlchemy Core tables for inventory. Must stay in sync with migration 0002."""

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

areas = Table(
    "areas",
    metadata,
    Column("id", String(8), primary_key=True),
    Column("name_en", Text, nullable=False),
    Column("name_ar", Text, nullable=False),
    Column("type", String(16), nullable=False),
    Column("base_price_per_m2_2015", Integer, nullable=False),
    Column("liquidity_tier", Integer, nullable=False),
    Column("gross_rental_yield_base", Float, nullable=False),
)

developers = Table(
    "developers",
    metadata,
    Column("id", String(8), primary_key=True),
    Column("name_en", Text, nullable=False),
    Column("tier", String(1), nullable=False),
    Column("on_time_delivery_rate", Float, nullable=False),
)

projects = Table(
    "projects",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("name_en", Text, nullable=False),
    Column("name_ar", Text, nullable=False),
    Column("area_id", String(8), ForeignKey("areas.id"), nullable=False, index=True),
    Column("developer_id", String(8), ForeignKey("developers.id"), nullable=False),
    Column("launch_year", Integer, nullable=False),
    Column("delivery_year", Integer, nullable=False),
    Column("amenities", Text, nullable=False, server_default=""),  # pipe-separated tags
)

units = Table(
    "units",
    metadata,
    Column("code", String(32), primary_key=True),
    Column("project_id", String(16), ForeignKey("projects.id"), nullable=False, index=True),
    Column("type", String(16), nullable=False),
    Column("bedrooms", Integer, nullable=False),
    Column("bua_m2", Float, nullable=False),
    Column("garden_m2", Float, nullable=False),
    Column("floor", Integer, nullable=False),
    Column("finishing", String(16), nullable=False),
    Column("delivery_year", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("price_egp", BigInteger, nullable=False),
    Column("view", String(32), nullable=False),
    Index("ix_units_status_price", "status", "price_egp"),
)

payment_plans = Table(
    "payment_plans",
    metadata,
    Column("id", String(24), primary_key=True),
    Column("project_id", String(16), ForeignKey("projects.id"), nullable=False, index=True),
    Column("name", Text, nullable=False),
    Column("down_payment_pct", Float, nullable=False),
    Column("years", Integer, nullable=False),
    Column("frequency", String(16), nullable=False),
    Column("delivery_payment_pct", Float, nullable=False),
    Column("maintenance_pct", Float, nullable=False),
    Column("cash_discount_pct", Float, nullable=False),
)
