from typing import Protocol

from reic.modules.handoff.domain.models import Lead


class LeadNotifier(Protocol):
    async def notify(self, lead: Lead) -> None:
        """Tell the broker side about a new lead. Implementations must not raise."""
        ...
