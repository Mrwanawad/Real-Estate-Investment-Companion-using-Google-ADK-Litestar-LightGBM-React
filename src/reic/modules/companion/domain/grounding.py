"""Grounding check: every material number in an answer must trace back to a tool result.

Numbers are compared loosely (rounding, "3.2M" vs 3,200,000, 12% vs 0.12), because the model
rephrases figures. Small integers (years, counts, bedrooms) are ignored.
"""

import re
from collections.abc import Iterable
from typing import Any

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%|k|m|mn|million|bn|billion|ألف|مليون)?",
    re.IGNORECASE,
)
_SCALE = {
    "k": 1e3,
    "ألف": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "مليون": 1e6,
    "bn": 1e9,
    "billion": 1e9,
}
MIN_MATERIAL = 100.0  # below this, numbers are years, counts or small percentages handled apart
REL_TOLERANCE = 0.06


def extract_numbers(text: str) -> list[tuple[float, bool]]:
    """(value, is_percent) for each number in `text`."""
    found: list[tuple[float, bool]] = []
    for match in _NUMBER.finditer(text.translate(_ARABIC_DIGITS)):
        whole, frac, unit = match.groups()
        value = float(whole.replace(",", "") + (f".{frac}" if frac else ""))
        unit = (unit or "").lower()
        if unit == "%":
            found.append((value, True))
            continue
        value *= _SCALE.get(unit, 1.0)
        found.append((value, False))
    return found


def _walk(value: Any) -> Iterable[float]:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        yield float(value)
    elif isinstance(value, str):
        try:
            yield float(value)
        except ValueError:  # labels like "5% down / 9 years" carry numbers too
            yield from (number for number, _ in extract_numbers(value))
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk(item)


def known_numbers(sources: Iterable[Any]) -> list[float]:
    """Every number in the tool results, plus x100 for fractions (0.12 -> 12%)."""
    numbers: list[float] = []
    for source in sources:
        for value in _walk(source):
            numbers.append(value)
            if -5 < value < 5:
                numbers.append(value * 100)
    return numbers


def _close(value: float, candidates: list[float]) -> bool:
    for known in candidates:
        if known == 0:
            continue
        if abs(value - known) / abs(known) <= REL_TOLERANCE:
            return True
    return False


def ungrounded_numbers(answer: str, sources: Iterable[Any]) -> list[float]:
    """Material numbers in `answer` with no close match in the tool results."""
    known = known_numbers(sources)
    missing: list[float] = []
    for value, is_percent in extract_numbers(answer):
        if not is_percent and value < MIN_MATERIAL:
            continue
        if 1990 <= value <= 2100 and float(value).is_integer() and not is_percent:
            continue  # a calendar year
        if is_percent and value < 1:
            continue
        if not _close(value, known):
            missing.append(value)
    return missing
