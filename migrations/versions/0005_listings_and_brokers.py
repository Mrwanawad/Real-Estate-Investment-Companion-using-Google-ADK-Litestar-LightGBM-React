"""Listing source links on units, the broker roster and lead assignment.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("source_url", sa.Text, nullable=True))
    op.create_table(
        "brokers",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("phone", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("languages", postgresql.JSONB, nullable=False),
        sa.Column("area_ids", postgresql.JSONB, nullable=False),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column("leads", sa.Column("broker_id", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "broker_id")
    op.drop_table("brokers")
    op.drop_column("units", "source_url")
