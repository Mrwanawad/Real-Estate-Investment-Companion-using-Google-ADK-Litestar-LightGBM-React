from typing import Any

from litestar import Controller, get
from litestar.exceptions import ValidationException

from reic.modules.knowledge.application.service import KnowledgeService


class KnowledgeController(Controller):
    """`knowledge_service` is injected by bootstrap."""

    path = "/knowledge"

    @get("/search", sync_to_thread=False)
    def search(
        self,
        knowledge_service: KnowledgeService,
        q: str,
        k: int = 4,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= k <= 20:
            raise ValidationException("k must be between 1 and 20")
        if language not in (None, "en", "ar"):
            raise ValidationException("language must be 'en' or 'ar'")
        return knowledge_service.search(q, k=k, language=language)
