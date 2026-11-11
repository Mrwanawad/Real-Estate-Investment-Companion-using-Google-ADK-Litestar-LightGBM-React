import json
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic import ValidationError as PydanticValidationError

from reic.modules.handoff.domain.errors import (
    InvalidStatusTransitionError,
    LeadNotFoundError,
    LeadValidationError,
)
from reic.modules.handoff.domain.models import Lead, check_status
from reic.modules.handoff.ports.lead_notifier import LeadNotifier
from reic.modules.handoff.ports.lead_store import LeadStore

MAX_LIMIT = 200
MAX_PROFILE_BYTES = 16_000


class NewLeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    language: str = Field(default="en", max_length=8)
    goal: str | None = None
    budget_egp: int | None = Field(default=None, le=10**12)
    profile: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(max_length=5000)
    unit_codes: list[Annotated[str, StringConstraints(max_length=64)]] = Field(
        default_factory=list, max_length=50
    )
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("profile")
    @classmethod
    def _profile_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str).encode()) > MAX_PROFILE_BYTES:
            raise ValueError(f"profile must be at most {MAX_PROFILE_BYTES} bytes as JSON")
        return value


class HandoffService:
    def __init__(self, store: LeadStore, notifier: LeadNotifier) -> None:
        self._store = store
        self._notifier = notifier

    async def create_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = NewLeadInput.model_validate(data)
        except PydanticValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'body'}: {e['msg']}" for e in exc.errors()
            )
            raise LeadValidationError(problems) from exc
        lead = Lead.create(**parsed.model_dump())
        await self._store.add(lead)
        await self._notifier.notify(lead)
        return {"lead_id": lead.id, "status": lead.status}

    async def list_leads(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if status is not None:
            check_status(status)
        leads = await self._store.list(status, max(1, min(limit, MAX_LIMIT)))
        return [lead.to_dict() for lead in leads]

    async def update_status(self, lead_id: str, status: str) -> dict[str, Any]:
        lead = await self._store.get(lead_id)
        if lead is None:
            raise LeadNotFoundError(lead_id)
        previous = lead.status
        lead.move_to(status)
        if not await self._store.save_status(lead, previous):
            # Another request moved the lead first.
            raise InvalidStatusTransitionError(previous, status)
        return lead.to_dict()
