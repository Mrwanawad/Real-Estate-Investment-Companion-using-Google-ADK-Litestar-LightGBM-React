"""SQLAlchemy Core table for leads. Must stay in sync with migration 0003."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    MetaData,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

leads = Table(
    "leads",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("status", String(16), nullable=False, server_default="new"),
    Column("name", Text),
    Column("phone", Text),
    Column("email", Text),
    Column("language", String(8), nullable=False, server_default="en"),
    Column("goal", String(16)),
    Column("budget_egp", BigInteger),
    Column("profile", JSONB, nullable=False),
    Column("summary", Text, nullable=False),
    Column("unit_codes", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("session_id", String(64)),
    Index("ix_leads_status_created_at", "status", "created_at"),
)
