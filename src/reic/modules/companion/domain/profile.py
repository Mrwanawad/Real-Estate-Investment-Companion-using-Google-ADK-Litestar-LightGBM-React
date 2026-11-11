"""Buyer profile and the clarification policy. Pure: no framework imports."""

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

Goal = Literal["live", "rent", "resell"]
RiskTolerance = Literal["low", "medium", "high"]
Language = Literal["en", "ar"]

GOALS: tuple[str, ...] = ("live", "rent", "resell")
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high")

# What each step needs before the agent should run it. Anything missing is asked for,
# at most MAX_QUESTIONS at a time, most important first.
REQUIRED_FOR: dict[str, tuple[str, ...]] = {
    "shortlist": ("goal", "budget_egp"),
    "projection": ("goal", "budget_egp", "horizon_years"),
    "handoff": ("contact",),
}
MAX_QUESTIONS = 2


@dataclass(frozen=True, slots=True)
class BuyerProfile:
    language: Language = "en"
    goal: Goal | None = None
    budget_egp: int | None = None
    down_payment_egp: int | None = None
    monthly_capacity_egp: int | None = None
    horizon_years: int | None = None
    risk_tolerance: RiskTolerance | None = None
    areas: tuple[str, ...] = ()
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    unit_codes: tuple[str, ...] = field(default=())

    def merge(self, **changes: Any) -> "BuyerProfile":
        """New profile with every non-empty change applied; invalid values are dropped."""
        clean: dict[str, Any] = {}
        for key, value in changes.items():
            if value is None or value == "" or value == [] or value == ():
                continue
            if key == "goal" and value not in GOALS:
                continue
            if key == "risk_tolerance" and value not in RISK_LEVELS:
                continue
            if key in {"budget_egp", "down_payment_egp", "monthly_capacity_egp"}:
                value = int(value)
                if value <= 0:
                    continue
            if key == "horizon_years":
                value = int(value)
                if not 1 <= value <= 30:
                    continue
            if key in {"areas", "unit_codes"}:
                value = tuple(dict.fromkeys([*getattr(self, key), *value]))
            clean[key] = value
        return replace(self, **clean)

    @property
    def has_contact(self) -> bool:
        return bool(self.phone or self.email)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["areas"] = list(self.areas)
        data["unit_codes"] = list(self.unit_codes)
        return data


def missing_for(profile: BuyerProfile, step: str) -> list[str]:
    """Fields still needed for `step`, capped at MAX_QUESTIONS."""
    missing: list[str] = []
    for name in REQUIRED_FOR.get(step, ()):
        if name == "contact":
            if not profile.has_contact:
                missing.append("phone_or_email")
        elif getattr(profile, name) is None:
            missing.append(name)
    return missing[:MAX_QUESTIONS]
