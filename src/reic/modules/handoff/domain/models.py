import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from reic.modules.handoff.domain.errors import InvalidStatusTransitionError, LeadValidationError

STATUSES = ("new", "contacted", "qualified", "closed")
GOALS = ("live", "rent", "resell")

# Forward-only pipeline; "closed" is final. Re-sending the current status is a no-op.
_TRANSITIONS: dict[str, set[str]] = {
    "new": {"contacted", "qualified", "closed"},
    "contacted": {"qualified", "closed"},
    "qualified": {"closed"},
    "closed": set(),
}


def check_status(status: str) -> str:
    if status not in STATUSES:
        raise LeadValidationError(f"status must be one of {', '.join(STATUSES)}")
    return status


@dataclass
class Lead:
    id: str
    created_at: datetime
    updated_at: datetime
    status: str
    name: str | None
    phone: str | None
    email: str | None
    language: str
    goal: str | None
    budget_egp: int | None
    profile: dict[str, Any]
    summary: str
    unit_codes: list[str] = field(default_factory=list)
    session_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        summary: str,
        profile: dict[str, Any],
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        language: str = "en",
        goal: str | None = None,
        budget_egp: int | None = None,
        unit_codes: list[str] | None = None,
        session_id: str | None = None,
    ) -> "Lead":
        phone = (phone or "").strip() or None
        email = (email or "").strip() or None
        if not phone and not email:
            raise LeadValidationError("a phone or an email is required")
        if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
            raise LeadValidationError("email is not valid")
        if not summary.strip():
            raise LeadValidationError("summary is required")
        if goal is not None and goal not in GOALS:
            raise LeadValidationError(f"goal must be one of {', '.join(GOALS)}")
        if budget_egp is not None and budget_egp <= 0:
            raise LeadValidationError("budget_egp must be positive")
        now = datetime.now(UTC)
        return cls(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            status="new",
            name=(name or "").strip() or None,
            phone=phone,
            email=email,
            language=language,
            goal=goal,
            budget_egp=budget_egp,
            profile=profile,
            summary=summary.strip(),
            unit_codes=list(unit_codes or []),
            session_id=session_id,
        )

    def move_to(self, new_status: str) -> None:
        check_status(new_status)
        if new_status != self.status and new_status not in _TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(self.status, new_status)
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "language": self.language,
            "goal": self.goal,
            "budget_egp": self.budget_egp,
            "profile": self.profile,
            "summary": self.summary,
            "unit_codes": self.unit_codes,
            "session_id": self.session_id,
        }
