import logging
from typing import Any

from litestar import Litestar, Router, get
from litestar.config.cors import CORSConfig
from litestar.di import Provide

from reic import __version__
from reic.bootstrap.companion import build_chat_service
from reic.bootstrap.handoff import build_handoff_router, build_handoff_service
from reic.bootstrap.inventory import build_inventory_router
from reic.bootstrap.knowledge import build_knowledge_router, build_knowledge_service
from reic.bootstrap.market import build_market_router, build_market_service
from reic.bootstrap.rate_limit import build_rate_limit
from reic.bootstrap.reports import build_report_service
from reic.bootstrap.scenarios import build_scenarios_router
from reic.modules.companion.adapters.inbound.controller import ChatController, ReportController
from reic.modules.financing.adapters.inbound.controller import FinancingController
from reic.modules.scenarios.application.service import ScenarioService
from reic.shared.config import Settings
from reic.shared.db import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@get("/health", sync_to_thread=False)
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def _plugins(settings: Settings) -> list[Any]:
    if not settings.otel_enabled:
        return []
    from reic.shared.observability import build_otel_plugin

    return [build_otel_plugin()]


def create_app(settings: Settings | None = None) -> Litestar:
    settings = settings or Settings()
    session_factory = create_session_factory(create_engine(settings.database_url))
    market = build_market_service(session_factory)
    scenarios = ScenarioService()
    knowledge = build_knowledge_service(settings)
    handoff = build_handoff_service(session_factory, settings)
    reports = build_report_service()
    chat = build_chat_service(
        settings,
        session_factory,
        market=market,
        scenarios=scenarios,
        knowledge=knowledge,
        handoff=handoff,
        reports=reports,
    )
    chat_router = Router(
        path="/",
        route_handlers=[ChatController, ReportController],
        dependencies={"chat": Provide(lambda: chat, sync_to_thread=False)},
    )
    rate_limit = build_rate_limit(settings)
    return Litestar(
        route_handlers=[
            health,
            FinancingController,
            build_inventory_router(session_factory),
            build_market_router(market),
            build_scenarios_router(scenarios),
            build_knowledge_router(knowledge),
            build_handoff_router(handoff, settings),
            chat_router,
        ],
        cors_config=CORSConfig(allow_origins=settings.cors_origins),
        middleware=[rate_limit] if rate_limit else [],
        plugins=_plugins(settings),
        debug=settings.app_env == "dev",
    )


app = create_app()
