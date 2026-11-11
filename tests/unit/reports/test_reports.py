from typing import Any

import pytest

from reic.bootstrap.reports import build_report_service
from reic.modules.reports.adapters.outbound.jinja_renderer import JinjaHtmlRenderer
from reic.modules.reports.adapters.outbound.pdf_renderers import (
    NullPdfRenderer,
    build_pdf_renderer,
)
from reic.modules.reports.application.service import ReportService
from reic.modules.reports.domain.formatting import money, percent, to_float

PAYLOAD: dict[str, Any] = {
    "language": "en",
    "generated_at": "2026-11-11 10:00",
    "profile": {
        "goal": "rental_income",
        "budget_egp": 6500000,
        "down_payment_egp": "1300000",
        "monthly_capacity_egp": 60000,
        "horizon_years": 7,
        "risk_tolerance": "medium",
        "areas": ["New Cairo", "Sheikh Zayed"],
    },
    "shortlist": [
        {
            "code": "NC-0042",
            "project_name": "Palm Court <Demo>",
            "area_name": "New Cairo",
            "type": "apartment",
            "bedrooms": 3,
            "bua_m2": 165,
            "price_egp": "6250000.00",
            "delivery_year": 2029,
            "score": 0.82,
            "reasons": ["within budget", "high rental demand"],
        }
    ],
    "financing": {
        "unit_code": "NC-0042",
        "price_egp": "6250000",
        "cheapest_label": "Developer 8y",
        "options": [
            {
                "label": "Developer 8y",
                "kind": "installments",
                "upfront": "625000",
                "avg_monthly_outflow": "58593.75",
                "total_nominal": "6250000",
                "present_value": "4210000.5",
            },
            {
                "label": "Mortgage 15y",
                "kind": "mortgage",
                "upfront": "1250000",
                "avg_monthly_outflow": 74000,
                "total_nominal": 8900000,
                "present_value": 5120000,
            },
        ],
    },
    "projection": {
        "unit_code": "NC-0042",
        "horizon_years": 7,
        "value": {"p10": 7000000, "p50": 9100000, "p90": 11800000},
        "value_path": [
            {
                "year": 2026 + i,
                "p10": 6.2e6 + i * 1e5,
                "p50": 6.3e6 + i * 4e5,
                "p90": 6.4e6 + i * 8e5,
            }
            for i in range(8)
        ],
        "rent": {"monthly_p50": 38000, "gross_yield": 0.073},
        "irr": {"p10": 0.04, "p50": 0.11, "p90": 0.18},
        "prob_loss": 0.07,
        "break_even_year": 2031,
        "sensitivity": [
            {"driver": "Price growth", "low": 7.5e6, "high": 11.2e6},
            {"driver": "Delivery delay", "low": 8.4e6, "high": 9.3e6},
        ],
    },
    "risks": {
        "items": [
            {
                "kind": "delivery",
                "level": "high",
                "explanation_en": "Developer delivered late on past projects.",
                "explanation_ar": "تأخر المطور في تسليم مشروعات سابقة.",
            }
        ]
    },
    "citations": {
        "items": [
            {
                "doc_id": "delivery-delay-compensation-en",
                "title": "Delivery Delay Compensation",
                "snippet": "Compensation of 0.5% per month after the grace period.",
            }
        ]
    },
}

DISCLAIMER_EN = "SYNTHETIC DATA — NOT INVESTMENT ADVICE"


@pytest.fixture(scope="module")
def service() -> ReportService:
    return build_report_service()


def test_english_full_payload(service: ReportService) -> None:
    html = service.render_html(PAYLOAD, "en")
    assert 'lang="en"' in html and 'dir="ltr"' in html
    assert DISCLAIMER_EN in html
    assert html.count("<svg") == 3
    assert "6,250,000" in html and "4,210,001" in html
    assert "Palm Court &lt;Demo&gt;" in html  # escaped
    assert "Developer delivered late" in html
    assert "7.3%" in html and "GFS Didot" in html
    assert "delivery-delay-compensation-en" in html


def test_arabic_full_payload_is_rtl(service: ReportService) -> None:
    html = service.render_html(PAYLOAD, "ar")
    assert 'lang="ar"' in html and 'dir="rtl"' in html
    assert "بيانات وهمية — ليست نصيحة استثمارية" in html
    assert "تأخر المطور في تسليم مشروعات سابقة." in html
    assert "Developer delivered late" not in html
    assert html.count("<svg") == 3
    assert "6,250,000" in html


@pytest.mark.parametrize(
    ("language", "disclaimer"), [("en", DISCLAIMER_EN), ("ar", "بيانات وهمية")]
)
def test_empty_payload(service: ReportService, language: str, disclaimer: str) -> None:
    html = service.render_html({}, language)
    assert disclaimer in html
    assert "<svg" not in html
    assert 'id="profile"' not in html and 'id="risks"' not in html
    assert ("rtl" in html) == (language == "ar")


def test_partial_payload_renders_only_present_sections(service: ReportService) -> None:
    html = service.render_html({"profile": {"goal": "resale"}, "risks": {"items": []}}, "en")
    assert 'id="profile"' in html
    assert 'id="shortlist"' not in html and 'id="risks"' not in html
    assert "No sections were provided" not in html


def test_no_blue_or_neon_colours(service: ReportService) -> None:
    html = service.render_html(PAYLOAD, "en")
    assert "JetBrains" not in html
    assert not any(c in html.lower() for c in ("#00f", "#0ff", "blue", "rgb("))


def test_pdf_falls_back_to_none_without_engine() -> None:
    service = ReportService(JinjaHtmlRenderer(), NullPdfRenderer())
    assert service.pdf_available is False
    assert service.render_pdf(PAYLOAD, "en") is None


def test_build_pdf_renderer_never_raises() -> None:
    renderer = build_pdf_renderer()
    assert isinstance(renderer.available, bool)


def test_formatting_helpers() -> None:
    assert money("1234567.5") == "1,234,568"
    assert money(None) == "-"
    assert to_float("1,250") == 1250.0
    assert percent(0.073) == "7.3%"
    assert percent(12) == "12.0%"


@pytest.mark.pdf
def test_real_pdf() -> None:
    service = build_report_service()
    if not service.pdf_available:
        pytest.skip("WeasyPrint system libraries not available")
    pdf = service.render_pdf(PAYLOAD, "ar")
    assert pdf is not None and pdf.startswith(b"%PDF")
