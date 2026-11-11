class NullPdfRenderer:
    """Used when WeasyPrint or its system libraries (GTK/Pango) are missing."""

    available = False

    def render(self, html: str) -> bytes | None:
        return None


class WeasyPrintRenderer:
    available = True

    def __init__(self, html_class: type) -> None:
        self._html_class = html_class

    def render(self, html: str) -> bytes | None:
        return self._html_class(string=html).write_pdf()


def build_pdf_renderer() -> WeasyPrintRenderer | NullPdfRenderer:
    """WeasyPrint is imported lazily; without GTK the import raises OSError."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return NullPdfRenderer()
    return WeasyPrintRenderer(HTML)
