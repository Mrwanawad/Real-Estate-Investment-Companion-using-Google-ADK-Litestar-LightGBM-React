"""Inline SVG charts, plain greyscale, no scripts. Every function returns an <svg> string."""

from html import escape
from typing import Any

from reic.modules.reports.domain.formatting import compact_money, money, to_float

FONT = "'Times New Roman', Times, serif"
INK, MID, LIGHT, FAINT = "#111111", "#6b6b6b", "#bdbdbd", "#e6e6e6"


def _svg(width: int, height: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{escape(title)}" '
        f'font-family="{FONT}" font-size="12" fill="{INK}">'
        f"<title>{escape(title)}</title>{body}</svg>"
    )


def _text(x: float, y: float, content: str, anchor: str = "start", bold: bool = False) -> str:
    weight = ' font-weight="bold"' if bold else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{weight}>{escape(content)}</text>'


def _ticks(low: float, high: float, count: int = 4) -> list[float]:
    if high == low:
        high = low + 1
    return [low + (high - low) * i / count for i in range(count + 1)]


def fan_chart(path: list[dict[str, Any]], title: str, labels: tuple[str, str, str]) -> str:
    """Value path by year: P10-P90 band, P50 line. `labels` are the P10, P50, P90 captions."""
    rows = []
    for row in path:
        values = [to_float(row.get(k)) for k in ("year", "p10", "p50", "p90")]
        if None not in values:
            rows.append(values)
    if not rows:
        return ""
    width, height, left, right, top, bottom = 640, 300, 64, 24, 20, 56
    years = [r[0] for r in rows]
    low = min(r[1] for r in rows)
    high = max(r[3] for r in rows)
    pad = (high - low) * 0.08 or 1.0
    low, high = max(0.0, low - pad), high + pad
    x0, x1 = min(years), max(years)

    def px(year: float) -> float:
        return left + (year - x0) / ((x1 - x0) or 1) * (width - left - right)

    def py(value: float) -> float:
        return top + (high - value) / (high - low) * (height - top - bottom)

    body = []
    for tick in _ticks(low, high):
        y = py(tick)
        body.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{FAINT}"/>'
        )
        body.append(_text(left - 8, y + 4, compact_money(tick), "end"))
    upper = [f"{px(r[0]):.1f},{py(r[3]):.1f}" for r in rows]
    lower = [f"{px(r[0]):.1f},{py(r[1]):.1f}" for r in reversed(rows)]
    body.append(f'<polygon points="{" ".join(upper + lower)}" fill="{FAINT}" stroke="{LIGHT}"/>')
    for index, key_color, dash in ((1, MID, "4 3"), (3, MID, "4 3")):
        points = " ".join(f"{px(r[0]):.1f},{py(r[index]):.1f}" for r in rows)
        body.append(
            f'<polyline points="{points}" fill="none" stroke="{key_color}" '
            f'stroke-width="1.2" stroke-dasharray="{dash}"/>'
        )
    mid = " ".join(f"{px(r[0]):.1f},{py(r[2]):.1f}" for r in rows)
    body.append(f'<polyline points="{mid}" fill="none" stroke="{INK}" stroke-width="2.2"/>')
    step = max(1, len(rows) // 8)
    for i, row in enumerate(rows):
        if i % step == 0 or i == len(rows) - 1:
            body.append(_text(px(row[0]), height - bottom + 18, f"{row[0]:.0f}", "middle"))
    legend_y = height - 10
    for i, (caption, color) in enumerate(zip(labels, (MID, INK, MID), strict=True)):
        x = left + i * 120
        body.append(
            f'<line x1="{x}" x2="{x + 22}" y1="{legend_y - 4}" y2="{legend_y - 4}" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        body.append(_text(x + 28, legend_y, caption))
    return _svg(width, height, "".join(body), title)


def bar_chart(items: list[tuple[str, Any]], title: str, highlight: str | None = None) -> str:
    """Horizontal bars (value labelled at the bar end). `highlight` darkens one bar."""
    rows = [(label, to_float(value)) for label, value in items]
    rows = [(label, value) for label, value in rows if value is not None]
    if not rows:
        return ""
    row_h, left, right, top = 34, 190, 90, 10
    width = 640
    height = top * 2 + row_h * len(rows)
    biggest = max(value for _, value in rows) or 1.0
    body = []
    for i, (label, value) in enumerate(rows):
        y = top + i * row_h
        length = max(1.0, value / biggest * (width - left - right))
        color = INK if label == highlight else LIGHT
        body.append(_text(left - 10, y + 20, label, "end", bold=label == highlight))
        body.append(
            f'<rect x="{left}" y="{y + 6}" width="{length:.1f}" height="20" fill="{color}"/>'
        )
        body.append(_text(left + length + 8, y + 20, money(value)))
    return _svg(width, height, "".join(body), title)


def tornado(
    items: list[dict[str, Any]], title: str, base: float | None, labels: tuple[str, str]
) -> str:
    """Sensitivity bars around `base`; each item is {driver, low, high} (outcomes at the low
    and high setting of the driver). Widest swing on top."""
    rows = []
    for item in items:
        low, high = to_float(item.get("low")), to_float(item.get("high"))
        if low is not None and high is not None:
            rows.append((str(item.get("driver", "")), low, high))
    if not rows:
        return ""
    if base is None:
        base = sum((low + high) / 2 for _, low, high in rows) / len(rows)
    rows.sort(key=lambda r: -abs(r[2] - r[1]))
    left, right, top, row_h, width = 190, 70, 24, 32, 640
    lo = min(min(r[1], r[2]) for r in rows + [("", base, base)])
    hi = max(max(r[1], r[2]) for r in rows + [("", base, base)])
    span = (hi - lo) or 1.0
    start = left + 60
    plot = width - start - right

    def px(value: float) -> float:
        return start + (value - lo) / span * plot

    height = top + row_h * len(rows) + 30
    body = [
        _text(left, 14, labels[0]),
        _text(width - right, 14, labels[1], "end"),
    ]
    for i, (driver, low, high) in enumerate(rows):
        y = top + i * row_h
        body.append(_text(left - 10, y + 19, driver, "end"))
        for value, color in ((low, MID), (high, LIGHT)):
            a, b = sorted((px(base), px(value)))
            body.append(
                f'<rect x="{a:.1f}" y="{y + 5}" width="{max(1.0, b - a):.1f}" '
                f'height="20" fill="{color}"/>'
            )
        left_val, right_val = sorted((low, high))
        body.append(_text(px(left_val) - 6, y + 19, money(left_val), "end"))
        body.append(_text(px(right_val) + 6, y + 19, money(right_val)))
    axis = px(base)
    body.append(
        f'<line x1="{axis:.1f}" x2="{axis:.1f}" y1="{top - 2}" '
        f'y2="{top + row_h * len(rows)}" stroke="{INK}" stroke-width="1.5"/>'
    )
    body.append(_text(axis, height - 8, money(base), "middle", bold=True))
    return _svg(width, height, "".join(body), title)
