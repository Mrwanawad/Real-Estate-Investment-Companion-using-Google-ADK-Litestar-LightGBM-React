"""Broker roster and lead assignment. Pure: no framework imports."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Broker:
    id: str
    name: str
    phone: str
    email: str
    languages: tuple[str, ...]
    areas: tuple[str, ...]  # area names in English and Arabic
    simulated: bool = True

    def covers(self, wanted: Iterable[str]) -> bool:
        mine = [a.casefold() for a in self.areas]
        return any(w.casefold() in a or a in w.casefold() for w in wanted if w for a in mine)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "simulated": self.simulated,
        }


def pick_broker(
    brokers: Sequence[Broker],
    language: str,
    areas: Sequence[str],
    open_leads: Mapping[str, int],
) -> Broker | None:
    """The least busy broker who speaks the buyer's language and covers one of their areas.

    Falls back to any broker who speaks the language, then to anyone. Ties go to the lowest id.
    """
    speaking = [b for b in brokers if language in b.languages]
    for pool in ([b for b in speaking if b.covers(areas)], speaking, list(brokers)):
        if pool:
            return min(pool, key=lambda b: (open_leads.get(b.id, 0), b.id))
    return None
