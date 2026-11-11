from typing import Any

from reic.modules.reports.ports.renderers import HtmlRenderer, PdfRenderer


class ReportService:
    """Renders a report payload to HTML, and to PDF when a PDF engine is available."""

    def __init__(self, html: HtmlRenderer, pdf: PdfRenderer) -> None:
        self._html = html
        self._pdf = pdf

    @property
    def pdf_available(self) -> bool:
        return self._pdf.available

    def render_html(self, payload: dict[str, Any], language: str = "en") -> str:
        return self._html.render(payload, language)

    def render_pdf(self, payload: dict[str, Any], language: str = "en") -> bytes | None:
        if not self._pdf.available:
            return None
        return self._pdf.render(self.render_html(payload, language))
