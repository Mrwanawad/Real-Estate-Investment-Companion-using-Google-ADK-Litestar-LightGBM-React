"""What the companion needs from the rest of the system. Implemented in bootstrap.

Results are JSON-ready dicts in the artifact shapes the chat client renders.
"""

from typing import Any, Protocol


class CompanionBackend(Protocol):
    async def shortlist(self, criteria: dict[str, Any], goal: str, limit: int) -> dict[str, Any]:
        """{"units": [...]} in the shortlist artifact shape."""
        ...

    async def unit(self, code: str) -> dict[str, Any] | None:
        """Unit facts: code, price_egp, area_id, area_name, type, bedrooms, bua_m2, garden_m2,
        floor, finishing, delivery_year, developer_tier, developer_on_time_rate,
        liquidity_tier, plans [...]."""
        ...

    async def compare_financing(self, unit: dict[str, Any]) -> dict[str, Any]: ...

    async def project_returns(
        self, unit: dict[str, Any], horizon_years: int, goal: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """(projection artifact, risks artifact)."""
        ...

    async def search_knowledge(self, query: str, language: str) -> dict[str, Any]:
        """{"items": [{doc_id, title, snippet, text}]}."""
        ...

    async def create_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        """{"lead_id", "status"}."""
        ...


class ReportRenderer(Protocol):
    def render_html(self, payload: dict[str, Any], language: str) -> str: ...

    def render_pdf(self, payload: dict[str, Any], language: str) -> bytes | None: ...
