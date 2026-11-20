from reic.modules.inventory.domain.areas import AreaResolver
from reic.modules.inventory.domain.models import Area


def _area(area_id: str, en: str, ar: str) -> Area:
    return Area(area_id, en, ar, "urban", 10_000, 1, 0.05)


RESOLVER = AreaResolver(
    [
        _area("NC", "New Cairo", "القاهرة الجديدة"),
        _area("MD", "Madinaty", "مدينتي"),
        _area("SZ", "Sheikh Zayed", "الشيخ زايد"),
    ]
)


def test_mentions_in_free_text_any_language() -> None:
    assert RESOLVER.mentioned("معايا ٤ مليون وعايز أشتري للإيجار في مدينتي لمدة ٥ سنين") == ["MD"]
    assert RESOLVER.mentioned("Comparing Zayed with the 5th settlement") == ["SZ", "NC"]
    assert RESOLVER.mentioned("I have 5M EGP and want to rent it out") == []
