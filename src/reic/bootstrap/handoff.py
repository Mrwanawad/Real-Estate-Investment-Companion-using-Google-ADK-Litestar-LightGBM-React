"""Wiring for the handoff module: store, notifier, service and router."""

import logging

from litestar import Router
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.handoff.adapters.inbound.controller import (
    BrokerLeadsController,
    LeadsController,
)
from reic.modules.handoff.adapters.inbound.guards import broker_guard
from reic.modules.handoff.adapters.outbound.notifiers import HmacWebhookNotifier, NullNotifier
from reic.modules.handoff.adapters.outbound.sql_lead_store import SqlLeadStore
from reic.modules.handoff.application.service import HandoffService
from reic.modules.handoff.ports.lead_notifier import LeadNotifier
from reic.shared.config import Settings

logger = logging.getLogger(__name__)


def build_handoff_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> HandoffService:
    notifier: LeadNotifier = NullNotifier()
    secret = settings.webhook_secret.get_secret_value() if settings.webhook_secret else ""
    if settings.webhook_url and secret:
        notifier = HmacWebhookNotifier(settings.webhook_url, secret)
    elif settings.webhook_url:
        logger.warning("WEBHOOK_URL is set but WEBHOOK_SECRET is empty; lead webhook disabled")
    return HandoffService(SqlLeadStore(session_factory), notifier)


def build_handoff_router(service: HandoffService, settings: Settings) -> Router:
    api_key = settings.broker_api_key.get_secret_value() if settings.broker_api_key else None
    broker = Router(
        path="/broker",
        route_handlers=[BrokerLeadsController],
        guards=[broker_guard(api_key)],
    )
    return Router(
        path="/",
        route_handlers=[LeadsController, broker],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
    )
