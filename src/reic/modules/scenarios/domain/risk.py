"""Rule-based risk summary. Levels are "low" < "medium" < "high".

Thresholds:
- delivery: already delivered (years_to_delivery == 0) -> low. Otherwise developer on-time rate
  >= 0.80 low, >= 0.60 medium, else high; a wait of 4+ years moves it one level up.
- liquidity: tier 1 low, tier 2 medium, tier 3 high.
- price: simulated P50 value at horizon below the price -> high; only P10 below the price ->
  medium; else low.
- currency_inflation: probability of a real (inflation-adjusted) loss >= 0.50 high, >= 0.25
  medium, else low. Every asset is EGP-denominated, so this risk is always reported.
"""

from dataclasses import dataclass
from typing import Any

LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class RiskInputs:
    developer_on_time_rate: float
    years_to_delivery: int
    liquidity_tier: int
    price_egp: float
    value_p10: float
    value_p50: float
    prob_real_loss: float


def _bump(level: str) -> str:
    return LEVELS[min(LEVELS.index(level) + 1, 2)]


def _item(kind: str, level: str, en: str, ar: str) -> dict[str, str]:
    return {"kind": kind, "level": level, "explanation_en": en, "explanation_ar": ar}


def _delivery(r: RiskInputs) -> dict[str, str]:
    if r.years_to_delivery == 0:
        return _item(
            "delivery", "low", "The unit is already delivered.", "الوحدة تم تسليمها بالفعل."
        )
    rate = r.developer_on_time_rate
    level = "low" if rate >= 0.8 else "medium" if rate >= 0.6 else "high"
    if r.years_to_delivery >= 4:
        level = _bump(level)
    return _item(
        "delivery",
        level,
        f"The developer delivers on time {rate:.0%} of the time and delivery is "
        f"{r.years_to_delivery} year(s) away.",
        f"المطور يسلم في الموعد بنسبة {rate:.0%} والتسليم بعد {r.years_to_delivery} سنة.",
    )


def _liquidity(r: RiskInputs) -> dict[str, str]:
    return _item(
        "liquidity",
        LEVELS[r.liquidity_tier - 1],
        f"The area is liquidity tier {r.liquidity_tier} (1 is easiest to resell).",
        f"المنطقة في فئة سيولة {r.liquidity_tier} (الفئة 1 هي الأسهل في إعادة البيع).",
    )


def _price(r: RiskInputs) -> dict[str, str]:
    if r.value_p50 < r.price_egp:
        level = "high"
    elif r.value_p10 < r.price_egp:
        level = "medium"
    else:
        level = "low"
    return _item(
        "price",
        level,
        f"Estimated fair value today: median {r.value_p50:,.0f} and downside (P10) "
        f"{r.value_p10:,.0f} EGP against a price of {r.price_egp:,.0f}.",
        f"القيمة العادلة المقدّرة اليوم: الوسيط {r.value_p50:,.0f} والسيناريو الضعيف (P10) "
        f"{r.value_p10:,.0f} جنيه مقابل سعر {r.price_egp:,.0f}.",
    )


def _currency(r: RiskInputs) -> dict[str, str]:
    p = r.prob_real_loss
    level = "high" if p >= 0.45 else "medium" if p >= 0.2 else "low"
    return _item(
        "currency_inflation",
        level,
        f"The asset is priced in EGP; the chance of losing money after inflation is {p:.0%}.",
        f"الأصل بالجنيه المصري؛ احتمال الخسارة بعد احتساب التضخم {p:.0%}.",
    )


def summarize_risks(r: RiskInputs) -> list[dict[str, Any]]:
    return [_delivery(r), _liquidity(r), _price(r), _currency(r)]
