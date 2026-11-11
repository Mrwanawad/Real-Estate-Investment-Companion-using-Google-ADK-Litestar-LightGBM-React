from typing import Protocol

from reic.modules.handoff.domain.models import Lead


class LeadStore(Protocol):
    async def add(self, lead: Lead) -> None: ...

    async def get(self, lead_id: str) -> Lead | None: ...

    async def list(self, status: str | None, limit: int) -> list[Lead]:
        """Newest first, optionally filtered by status."""
        ...

    async def save_status(self, lead: Lead, expected_status: str) -> bool:
        """Persist status and updated_at only if the stored status is still `expected_status`.

        Returns False when another writer changed it first (compare-and-set).
        """
        ...
