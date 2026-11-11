"""Broker handoff leads.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("phone", sa.Text, nullable=True),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("goal", sa.String(16), nullable=True),
        sa.Column("budget_egp", sa.BigInteger, nullable=True),
        sa.Column("profile", postgresql.JSONB, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column(
            "unit_codes",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("session_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_leads_status_created_at", "leads", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("leads")
