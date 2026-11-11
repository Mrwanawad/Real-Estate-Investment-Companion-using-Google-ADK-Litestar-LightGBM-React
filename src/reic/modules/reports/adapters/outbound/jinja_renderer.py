from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from reic.modules.reports.domain.view import build_context

TEMPLATES = Path(__file__).parent / "templates"


class JinjaHtmlRenderer:
    def __init__(self, template: str = "report.html.j2") -> None:
        self._env = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=select_autoescape(["html", "j2"], default=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._template = template

    def render(self, payload: dict[str, Any], language: str) -> str:
        return self._env.get_template(self._template).render(**build_context(payload, language))
