from typing import Any

from litestar import Controller, post
from litestar.exceptions import ValidationException
from litestar.params import JSONBody

from reic.modules.scenarios.application.service import ScenarioService
from reic.modules.scenarios.domain.errors import ScenarioValidationError


class ScenariosController(Controller):
    """`service` is injected by bootstrap."""

    path = "/scenarios"

    @post("/simulate", status_code=200, sync_to_thread=True)
    def simulate(self, data: JSONBody[dict[str, Any]], service: ScenarioService) -> dict[str, Any]:
        try:
            return service.simulate(data)
        except ScenarioValidationError as exc:
            raise ValidationException(detail=str(exc)) from exc

    @post("/risk", status_code=200, sync_to_thread=False)
    def risk(self, data: JSONBody[dict[str, Any]], service: ScenarioService) -> dict[str, Any]:
        try:
            return service.risk_summary(data)
        except ScenarioValidationError as exc:
            raise ValidationException(detail=str(exc)) from exc
