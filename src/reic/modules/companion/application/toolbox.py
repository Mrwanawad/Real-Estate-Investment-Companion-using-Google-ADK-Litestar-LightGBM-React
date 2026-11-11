"""The agent's tools. Each tool records the artifacts it produces for the chat client and
returns a compact, model-facing summary. All numbers come from the backend, never the model."""

import functools
import logging
from dataclasses import dataclass, field
from typing import Any

from reic.modules.companion.domain.errors import ToolInputError
from reic.modules.companion.domain.profile import BuyerProfile, missing_for
from reic.modules.companion.ports.backend import CompanionBackend
from reic.modules.companion.ports.engine import ToolFunction

log = logging.getLogger(__name__)


def _safe(fn: ToolFunction) -> ToolFunction:
    """A failing backend call becomes an error result the model can explain, not a dead turn."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except Exception:
            log.exception("tool %s failed", fn.__name__)
            return {"error": f"{fn.__name__} is temporarily unavailable; tell the buyer"}

    return wrapper


@dataclass
class SessionState:
    session_id: str
    profile: BuyerProfile
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    lead_id: str | None = None


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


class ToolBox:
    def __init__(
        self, state: SessionState, backend: CompanionBackend, *, pdf_available: bool = False
    ) -> None:
        self._state = state
        self._backend = backend
        self._pdf_available = pdf_available
        self.pending: list[tuple[str, dict[str, Any]]] = []
        self.results: list[dict[str, Any]] = []  # this turn's tool results, for grounding

    @property
    def profile(self) -> BuyerProfile:
        return self._state.profile

    def _emit(self, kind: str, data: dict[str, Any]) -> None:
        self._state.artifacts[kind] = data
        self.pending.append((kind, data))

    def _done(self, result: dict[str, Any]) -> dict[str, Any]:
        self.results.append(result)
        return result

    async def _unit(self, unit_code: str) -> dict[str, Any]:
        unit = await self._backend.unit(unit_code.strip().upper())
        if unit is None:
            raise ToolInputError(f"unit {unit_code} not found; use a code from search_units")
        return unit

    def tools(self) -> dict[str, ToolFunction]:
        tools: dict[str, ToolFunction] = {
            "update_profile": self.update_profile,
            "search_units": self.search_units,
            "compare_financing": self.compare_financing,
            "project_returns": self.project_returns,
            "search_knowledge": self.search_knowledge,
            "create_lead": self.create_lead,
            "build_report": self.build_report,
        }
        return {name: _safe(fn) for name, fn in tools.items()}

    async def update_profile(
        self,
        goal: str | None = None,
        budget_egp: int | None = None,
        down_payment_egp: int | None = None,
        monthly_capacity_egp: int | None = None,
        horizon_years: int | None = None,
        risk_tolerance: str | None = None,
        areas: list[str] | None = None,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Save what the buyer told you about themselves. Call it whenever you learn something.

        Args:
            goal: "live", "rent" or "resell".
            budget_egp: Total budget in Egyptian pounds (e.g. 5000000 for 5M).
            down_payment_egp: Cash available now for the down payment, in EGP.
            monthly_capacity_egp: What the buyer can pay per month, in EGP.
            horizon_years: How many years the buyer plans to hold the unit.
            risk_tolerance: "low", "medium" or "high".
            areas: Preferred areas, in English or Arabic.
            name: Buyer name, only if given.
            phone: Buyer phone, only if given.
            email: Buyer email, only if given.

        Returns:
            The saved profile and the fields still missing for a shortlist and a projection.
        """
        self._state.profile = self.profile.merge(
            goal=goal,
            budget_egp=budget_egp,
            down_payment_egp=down_payment_egp,
            monthly_capacity_egp=monthly_capacity_egp,
            horizon_years=horizon_years,
            risk_tolerance=risk_tolerance,
            areas=areas or (),
            name=name,
            phone=phone,
            email=email,
        )
        return {
            "profile": self.profile.to_dict(),
            "missing_for_shortlist": missing_for(self.profile, "shortlist"),
            "missing_for_projection": missing_for(self.profile, "projection"),
        }

    async def search_units(
        self,
        budget_max_egp: int | None = None,
        areas: list[str] | None = None,
        unit_types: list[str] | None = None,
        bedrooms_min: int | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Find and rank available units that fit the buyer's goal and budget.

        Args:
            budget_max_egp: Maximum total price in EGP. Defaults to the profile budget.
            areas: Area names or ids to search. Defaults to the profile areas (all if empty).
            unit_types: Any of apartment, duplex, townhouse, twin_house, villa, chalet.
            bedrooms_min: Minimum number of bedrooms.
            limit: Number of units to return (1-5).

        Returns:
            Ranked units with code, price, area, delivery year, score and reasons.
        """
        profile = self.profile
        missing = missing_for(profile.merge(budget_egp=budget_max_egp), "shortlist")
        if missing:
            return _error(f"ask the buyer for: {', '.join(missing)}")
        criteria = {
            "budget_max_egp": budget_max_egp or profile.budget_egp,
            "down_payment_available_egp": profile.down_payment_egp,
            "monthly_capacity_egp": profile.monthly_capacity_egp,
            "areas": list(areas or profile.areas),
            "types": list(unit_types or ()),
            "bedrooms_min": bedrooms_min,
        }
        try:
            result = await self._backend.shortlist(
                criteria, profile.goal or "live", max(1, min(limit, 5))
            )
        except ValueError as exc:
            return _error(str(exc))
        units = result.get("units", [])
        if not units:
            return self._done({"units": [], "note": "no available unit matches; relax a filter"})
        self._emit("shortlist", result)
        self._state.profile = profile.merge(unit_codes=[u["code"] for u in units])
        return self._done(
            {
                "units": [
                    {
                        k: u.get(k)
                        for k in (
                            "code",
                            "project_name",
                            "area_name",
                            "type",
                            "bedrooms",
                            "bua_m2",
                            "price_egp",
                            "delivery_year",
                            "developer_tier",
                            "score",
                            "reasons",
                        )
                    }
                    for u in units
                ]
            }
        )

    async def compare_financing(self, unit_code: str) -> dict[str, Any]:
        """Compare paying cash, the developer installment plans and a bank mortgage for a unit.

        Args:
            unit_code: Unit code from search_units.

        Returns:
            Upfront, average monthly outflow, total paid and present value for each option.
        """
        try:
            unit = await self._unit(unit_code)
        except ToolInputError as exc:
            return _error(str(exc))
        result = await self._backend.compare_financing(unit)
        self._emit("financing", result)
        return self._done(result)

    async def project_returns(
        self, unit_code: str, horizon_years: int | None = None
    ) -> dict[str, Any]:
        """Project resale value, rental income and risks for a unit over the buyer's horizon.

        Runs the market models and a Monte Carlo simulation; returns P10/P50/P90 ranges,
        probability of loss, break-even year and a rule-based risk summary.

        Args:
            unit_code: Unit code from search_units.
            horizon_years: Holding period in years. Defaults to the profile horizon.
        """
        horizon = horizon_years or self.profile.horizon_years
        if horizon is None:
            return _error("ask the buyer for: horizon_years")
        try:
            unit = await self._unit(unit_code)
        except ToolInputError as exc:
            return _error(str(exc))
        projection, risks = await self._backend.project_returns(
            unit, int(horizon), self.profile.goal or "live"
        )
        self._emit("projection", projection)
        self._emit("risks", risks)
        language = self.profile.language
        summary = {
            k: projection.get(k)
            for k in (
                "unit_code",
                "horizon_years",
                "value",
                "rent",
                "irr",
                "prob_loss",
                "break_even_year",
            )
        }
        summary["risks"] = [
            {
                "kind": r["kind"],
                "level": r["level"],
                "explanation": r.get(f"explanation_{language}") or r.get("explanation_en"),
            }
            for r in risks.get("items", [])
        ]
        return self._done(summary)

    async def search_knowledge(self, query: str) -> dict[str, Any]:
        """Search company documents (contracts, policies, fees, mortgage rules, FAQ).

        Use it for any question about rules, fees, cancellation, delivery or paperwork,
        and cite the returned sources as [1], [2]...

        Args:
            query: The question, in the buyer's language.
        """
        result = await self._backend.search_knowledge(query, self.profile.language)
        items = result.get("items", [])
        if items:
            self._emit(
                "citations",
                {"items": [{k: i[k] for k in ("doc_id", "title", "snippet")} for i in items]},
            )
        return self._done(
            {
                "sources": [
                    {"ref": n, "title": i["title"], "text": i.get("text", i["snippet"])}
                    for n, i in enumerate(items, start=1)
                ]
            }
        )

    async def create_lead(self, summary: str) -> dict[str, Any]:
        """Hand the buyer to a human broker. Needs the buyer's phone or email in the profile.

        Args:
            summary: Two or three sentences for the broker: goal, budget, units of interest.
        """
        profile = self.profile
        if not profile.has_contact:
            return _error("ask the buyer for a phone number or email first")
        if self._state.lead_id:
            return self._done({"lead_id": self._state.lead_id, "status": "already_created"})
        result = await self._backend.create_lead(
            {
                "name": profile.name,
                "phone": profile.phone,
                "email": profile.email,
                "language": profile.language,
                "goal": profile.goal,
                "budget_egp": profile.budget_egp,
                "profile": profile.to_dict(),
                "summary": summary,
                "unit_codes": list(profile.unit_codes),
                "session_id": self._state.session_id,
            }
        )
        self._state.lead_id = result["lead_id"]
        self._emit("handoff", result)
        return self._done(result)

    async def build_report(self) -> dict[str, Any]:
        """Prepare the shareable HTML/PDF report of everything discussed so far."""
        if not self._state.artifacts:
            return _error("nothing to report yet; shortlist units first")
        sid = self._state.session_id
        lang = self.profile.language
        result = {
            "url_html": f"/reports/{sid}?lang={lang}&format=html",
            "url_pdf": f"/reports/{sid}?lang={lang}&format=pdf" if self._pdf_available else None,
        }
        self._emit("report", result)
        return self._done({"report_ready": True})
