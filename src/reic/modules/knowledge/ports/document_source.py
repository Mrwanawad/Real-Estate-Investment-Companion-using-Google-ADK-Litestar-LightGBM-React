from typing import Protocol

from reic.modules.knowledge.domain.models import Document


class DocumentSource(Protocol):
    def load(self) -> list[Document]: ...
