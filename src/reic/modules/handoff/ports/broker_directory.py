from typing import Protocol

from reic.modules.handoff.domain.brokers import Broker


class BrokerDirectory(Protocol):
    async def brokers(self) -> list[Broker]: ...

    async def open_leads(self) -> dict[str, int]:
        """Leads not yet closed, per broker id."""
        ...
