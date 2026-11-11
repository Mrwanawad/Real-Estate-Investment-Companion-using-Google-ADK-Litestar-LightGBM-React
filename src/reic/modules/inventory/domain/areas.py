"""Resolve area names (English or Arabic, with aliases) to area ids."""

import re
from collections.abc import Iterable

from reic.modules.inventory.domain.models import Area

_DIACRITICS = re.compile("[ً-ٰٟـ]")  # harakat, superscript alef, tatweel
_ARABIC_CHARS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)

# Aliases are matched after normalisation, so spelling variants of the same Arabic word collapse.
AREA_ALIASES: dict[str, tuple[str, ...]] = {
    "NC": ("tagamoa", "fifth settlement", "5th settlement", "التجمع", "التجمع الخامس"),
    "SZ": ("zayed", "sheikh zayed city", "shaikh zayed", "زايد", "مدينة الشيخ زايد"),
    "OC": ("october", "6 october", "6th october", "sixth of october", "اكتوبر", "٦ أكتوبر"),
    "SH": ("sahel", "north coast", "الساحل"),
    "NA": ("new capital", "nac", "administrative capital", "العاصمة", "العاصمة الجديدة"),
    "MS": ("mostakbal", "mostaqbal city", "future city", "مستقبل", "المستقبل"),
    "MD": ("madinaty",),
    "MA": ("maadi", "al maadi", "el maadi"),
    "ZM": ("zamalek", "el zamalek"),
    "AL": ("alamein", "el alamein", "العلمين"),
    "SK": ("sokhna", "el sokhna", "السخنة"),
    "HE": ("heliopolis", "masr el gedida", "مصر الجديدة"),
}


def normalize(text: str) -> str:
    """Case-fold, strip diacritics, unify Arabic letter variants, drop the Arabic article."""
    text = _DIACRITICS.sub("", text).translate(_ARABIC_CHARS).casefold()
    cleaned = []
    for token in (t for t in _NON_WORD.split(text) if t):
        if token == "the":
            continue
        if token.startswith("ال") and len(token) > 3:
            token = token[2:]
        cleaned.append(token)
    return " ".join(cleaned)


class AreaResolver:
    def __init__(self, areas: Iterable[Area]) -> None:
        self._index: dict[str, str] = {}
        for area in areas:
            names = [area.id, area.name_en, area.name_ar, *AREA_ALIASES.get(area.id, ())]
            for name in names:
                self._index.setdefault(normalize(name), area.id)

    def resolve(self, text: str) -> str | None:
        """Return the area id for an id, English or Arabic name or alias; None if unknown."""
        key = normalize(text)
        if not key:
            return None
        if key in self._index:
            return self._index[key]
        # Fall back to a unique whole-word containment, e.g. "apartments in new cairo".
        padded = f" {key} "
        hits = {
            aid for name, aid in self._index.items() if len(name) >= 4 and f" {name} " in padded
        }
        return hits.pop() if len(hits) == 1 else None
