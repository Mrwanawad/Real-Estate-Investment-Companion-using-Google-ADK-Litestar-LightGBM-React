"""Wiring for the scenarios module: the service dependency plus the router."""

from litestar import Router
from litestar.di import Provide

from reic.modules.scenarios.adapters.inbound.controller import ScenariosController
from reic.modules.scenarios.application.service import ScenarioService


def build_scenarios_router(service: ScenarioService) -> Router:
    return Router(
        path="/",
        route_handlers=[ScenariosController],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
    )
