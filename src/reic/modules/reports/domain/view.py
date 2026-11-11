"""Turns a report payload (all sections optional) into the flat context the template renders."""

from typing import Any

from reic.modules.reports.domain.charts import bar_chart, fan_chart, tornado
from reic.modules.reports.domain.formatting import money, percent, plain, to_float
from reic.modules.reports.domain.labels import LABELS, normalize_language


def _profile(data: dict[str, Any], t: dict[str, str]) -> list[tuple[str, str]]:
    money_keys = ("budget_egp", "down_payment_egp", "monthly_capacity_egp")
    rows = [
        (t["goal"], plain(data.get("goal"))),
        (t["budget"], money(data.get("budget_egp"))),
        (t["down_payment"], money(data.get("down_payment_egp"))),
        (t["monthly_capacity"], money(data.get("monthly_capacity_egp"))),
        (t["horizon"], plain(data.get("horizon_years"))),
        (t["risk_tolerance"], plain(data.get("risk_tolerance"))),
        (t["areas"], ", ".join(map(str, data.get("areas") or [])) or "-"),
    ]
    keys = ("goal", *money_keys, "horizon_years", "risk_tolerance", "areas")
    return [row for row, key in zip(rows, keys, strict=True) if data.get(key) not in (None, "", [])]


def _shortlist(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "code": plain(u.get("code")),
            "project": plain(u.get("project_name")),
            "area": plain(u.get("area_name")),
            "type": plain(u.get("type")),
            "bedrooms": plain(u.get("bedrooms")),
            "bua": plain(u.get("bua_m2")),
            "price": money(u.get("price_egp")),
            "delivery": plain(u.get("delivery_year")),
            "score": plain(u.get("score")),
            "reasons": [str(r) for r in u.get("reasons") or []],
        }
        for u in items
    ]


def _financing(data: dict[str, Any], t: dict[str, str]) -> dict[str, Any]:
    options = data.get("options") or []
    cheapest = data.get("cheapest_label")
    return {
        "unit_code": plain(data.get("unit_code")),
        "price": money(data.get("price_egp")),
        "cheapest": plain(cheapest) if cheapest else None,
        "rows": [
            {
                "label": plain(o.get("label")),
                "kind": plain(o.get("kind")),
                "upfront": money(o.get("upfront")),
                "monthly": money(o.get("avg_monthly_outflow")),
                "total": money(o.get("total_nominal")),
                "pv": money(o.get("present_value")),
                "best": cheapest is not None and o.get("label") == cheapest,
            }
            for o in options
        ],
        "chart": bar_chart(
            [(str(o.get("label", "")), o.get("present_value")) for o in options],
            t["pv_chart"],
            highlight=cheapest,
        ),
    }


def _range(block: dict[str, Any] | None) -> str | None:
    if not block:
        return None
    return " / ".join(money(block.get(k)) for k in ("p10", "p50", "p90"))


def _projection(data: dict[str, Any], t: dict[str, str], language: str) -> dict[str, Any]:
    unit = "years"
    kpis: list[tuple[str, str]] = []
    value = _range(data.get("value"))
    if value:
        kpis.append((f"{t['value_range']} P10 / P50 / P90", value))
    rent = data.get("rent") or {}
    if rent.get("monthly_p50") is not None:
        kpis.append((t["rent"], money(rent["monthly_p50"])))
    if rent.get("gross_yield") is not None:
        kpis.append((t["gross_yield"], percent(rent["gross_yield"])))
    irr = data.get("irr")
    if irr:
        kpis.append(
            (
                f"{t['irr']} P10 / P50 / P90",
                " / ".join(percent(irr.get(k)) for k in ("p10", "p50", "p90")),
            )
        )
    if data.get("prob_loss") is not None:
        kpis.append((t["prob_loss"], percent(data["prob_loss"])))
    if data.get("break_even_year") is not None:
        kpis.append((t["break_even"], plain(data["break_even_year"])))
    p50 = to_float((data.get("value") or {}).get("p50"))
    return {
        "unit_code": plain(data.get("unit_code")),
        "horizon": plain(data.get("horizon_years")),
        "unit_label": t[unit],
        "kpis": kpis,
        "fan": fan_chart(data.get("value_path") or [], t["fan_chart"], ("P10", "P50", "P90")),
        "tornado": tornado(
            data.get("sensitivity") or [],
            t["tornado"],
            p50,
            (t["low_setting"], t["high_setting"]),
        ),
    }


def _risks(items: list[dict[str, Any]], t: dict[str, str], language: str) -> list[dict[str, str]]:
    key = "explanation_ar" if language == "ar" else "explanation_en"
    rows = []
    for item in items:
        level = str(item.get("level", ""))
        text = item.get(key) or item.get("explanation_en") or item.get("explanation_ar") or ""
        rows.append(
            {
                "kind": plain(item.get("kind")),
                "level": t.get(f"level_{level}", level),
                "level_raw": level,
                "text": str(text),
            }
        )
    return rows


def build_context(payload: dict[str, Any], language: str = "en") -> dict[str, Any]:
    lang = normalize_language(language)
    t = LABELS[lang]
    context: dict[str, Any] = {
        "lang": lang,
        "dir": "rtl" if lang == "ar" else "ltr",
        "t": t,
        "generated_at": payload.get("generated_at"),
        "profile": _profile(payload["profile"], t) if payload.get("profile") else None,
        "shortlist": _shortlist(payload["shortlist"]) if payload.get("shortlist") else None,
        "financing": _financing(payload["financing"], t) if payload.get("financing") else None,
        "projection": (
            _projection(payload["projection"], t, lang) if payload.get("projection") else None
        ),
        "risks": None,
        "citations": None,
    }
    risk_items = (payload.get("risks") or {}).get("items")
    if risk_items:
        context["risks"] = _risks(risk_items, t, lang)
    citation_items = (payload.get("citations") or {}).get("items")
    if citation_items:
        context["citations"] = [
            {
                "doc_id": str(c.get("doc_id", "")),
                "title": plain(c.get("title")),
                "snippet": str(c.get("snippet", "")),
            }
            for c in citation_items
        ]
    context["empty"] = not any(
        context[k]
        for k in ("profile", "shortlist", "financing", "projection", "risks", "citations")
    )
    return context
