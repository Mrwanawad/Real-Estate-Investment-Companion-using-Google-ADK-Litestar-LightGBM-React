"""Inventory and market tables.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.String(8), primary_key=True),
        sa.Column("name_en", sa.Text, nullable=False),
        sa.Column("name_ar", sa.Text, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("base_price_per_m2_2015", sa.Integer, nullable=False),
        sa.Column("liquidity_tier", sa.Integer, nullable=False),
        sa.Column("gross_rental_yield_base", sa.Float, nullable=False),
    )
    op.create_table(
        "developers",
        sa.Column("id", sa.String(8), primary_key=True),
        sa.Column("name_en", sa.Text, nullable=False),
        sa.Column("tier", sa.String(1), nullable=False),
        sa.Column("on_time_delivery_rate", sa.Float, nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("name_en", sa.Text, nullable=False),
        sa.Column("name_ar", sa.Text, nullable=False),
        sa.Column("area_id", sa.String(8), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("developer_id", sa.String(8), sa.ForeignKey("developers.id"), nullable=False),
        sa.Column("launch_year", sa.Integer, nullable=False),
        sa.Column("delivery_year", sa.Integer, nullable=False),
        sa.Column("amenities", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_projects_area_id", "projects", ["area_id"])
    op.create_table(
        "units",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(16), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("bedrooms", sa.Integer, nullable=False),
        sa.Column("bua_m2", sa.Float, nullable=False),
        sa.Column("garden_m2", sa.Float, nullable=False),
        sa.Column("floor", sa.Integer, nullable=False),
        sa.Column("finishing", sa.String(16), nullable=False),
        sa.Column("delivery_year", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("price_egp", sa.BigInteger, nullable=False),
        sa.Column("view", sa.String(32), nullable=False),
    )
    op.create_index("ix_units_project_id", "units", ["project_id"])
    op.create_index("ix_units_status_price", "units", ["status", "price_egp"])
    op.create_table(
        "payment_plans",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("project_id", sa.String(16), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("down_payment_pct", sa.Float, nullable=False),
        sa.Column("years", sa.Integer, nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("delivery_payment_pct", sa.Float, nullable=False),
        sa.Column("maintenance_pct", sa.Float, nullable=False),
        sa.Column("cash_discount_pct", sa.Float, nullable=False),
    )
    op.create_index("ix_payment_plans_project_id", "payment_plans", ["project_id"])

    # Market tables (used by the market module later).
    op.create_table(
        "area_price_index",
        sa.Column("month", sa.Date, nullable=False),
        sa.Column("area_id", sa.String(8), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("index_level", sa.Float, nullable=False),
        sa.Column("avg_price_per_m2", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("area_id", "month"),
    )
    op.create_table(
        "rental_listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_date", sa.Date, nullable=False),
        sa.Column("area_id", sa.String(8), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("bedrooms", sa.Integer, nullable=False),
        sa.Column("bua_m2", sa.Float, nullable=False),
        sa.Column("finishing", sa.String(16), nullable=False),
        sa.Column("furnished", sa.Boolean, nullable=False),
        sa.Column("monthly_rent_egp", sa.BigInteger, nullable=False),
    )
    op.create_index("ix_rental_listings_area_date", "rental_listings", ["area_id", "listing_date"])
    op.create_table(
        "macro_monthly",
        sa.Column("month", sa.Date, primary_key=True),
        sa.Column("cpi_yoy_pct", sa.Float, nullable=False),
        sa.Column("egp_per_usd", sa.Float, nullable=False),
        sa.Column("cbe_deposit_rate", sa.Float, nullable=False),
        sa.Column("cbe_lending_rate", sa.Float, nullable=False),
        sa.Column("provenance", sa.Text, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "macro_monthly",
        "rental_listings",
        "area_price_index",
        "payment_plans",
        "units",
        "projects",
        "developers",
        "areas",
    ):
        op.drop_table(table)
