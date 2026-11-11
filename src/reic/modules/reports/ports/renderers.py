from typing import Any, Protocol


class HtmlRenderer(Protocol):
    def render(self, payload: dict[str, Any], language: str) -> str: ...


class PdfRenderer(Protocol):
    available: bool

    def render(self, html: str) -> bytes | None:
        """PDF bytes, or None when this renderer cannot produce one."""
        ...
