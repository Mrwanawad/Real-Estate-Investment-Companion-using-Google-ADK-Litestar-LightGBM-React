from typing import Any

from litestar import Controller, get, patch, post
from litestar.exceptions import ClientException, NotFoundException, ValidationException
from litestar.params import JSONBody

from reic.modules.handoff.application.service import HandoffService
from reic.modules.handoff.domain.errors import (
    InvalidStatusTransitionError,
    LeadNotFoundError,
    LeadValidationError,
)


class LeadsController(Controller):
    """Public lead intake. `service` is injected by bootstrap."""

    path = "/leads"

    @post("/")
    async def create(
        self, data: JSONBody[dict[str, Any]], service: HandoffService
    ) -> dict[str, Any]:
        try:
            return await service.create_lead(data)
        except LeadValidationError as exc:
            raise ValidationException(detail=str(exc)) from exc


class BrokerLeadsController(Controller):
    """Broker queue; bootstrap mounts it behind the API-key guard."""

    path = "/leads"

    @get("/")
    async def list(
        self, service: HandoffService, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        try:
            return await service.list_leads(status, limit)
        except LeadValidationError as exc:
            raise ValidationException(detail=str(exc)) from exc

    @patch("/{lead_id:str}")
    async def update(
        self, lead_id: str, data: JSONBody[dict[str, Any]], service: HandoffService
    ) -> dict[str, Any]:
        status = data.get("status")
        if not isinstance(status, str):
            raise ValidationException(detail="status is required")
        try:
            return await service.update_status(lead_id, status)
        except LeadValidationError as exc:
            raise ValidationException(detail=str(exc)) from exc
        except LeadNotFoundError as exc:
            raise NotFoundException(detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise ClientException(detail=str(exc), status_code=409) from exc
