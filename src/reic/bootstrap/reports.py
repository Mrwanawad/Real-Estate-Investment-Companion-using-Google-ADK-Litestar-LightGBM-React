"""Wiring for the reports module: Jinja HTML renderer plus WeasyPrint (or the null renderer)."""

from reic.modules.reports.adapters.outbound.jinja_renderer import JinjaHtmlRenderer
from reic.modules.reports.adapters.outbound.pdf_renderers import build_pdf_renderer
from reic.modules.reports.application.service import ReportService


def build_report_service() -> ReportService:
    return ReportService(JinjaHtmlRenderer(), build_pdf_renderer())
