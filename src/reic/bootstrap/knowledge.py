"""Wiring for the knowledge module: corpus source, embedder choice, service and router."""

from pathlib import Path

from litestar import Router
from litestar.di import Provide

from reic.modules.knowledge.adapters.inbound.controller import KnowledgeController
from reic.modules.knowledge.adapters.outbound.hashing_embedder import HashingEmbedder
from reic.modules.knowledge.adapters.outbound.markdown_source import MarkdownDocumentSource
from reic.modules.knowledge.adapters.outbound.minilm_embedder import MiniLmEmbedder
from reic.modules.knowledge.application.service import KnowledgeService
from reic.modules.knowledge.ports.embedder import Embedder
from reic.shared.config import Settings

DOCS_DIR = Path(__file__).resolve().parents[3] / "demo_data" / "docs"


def build_embedder(name: str) -> Embedder:
    # bge-m3 is for local evaluation only; it falls back to MiniLM here.
    return HashingEmbedder() if name == "hashing" else MiniLmEmbedder()


def build_knowledge_service(settings: Settings) -> KnowledgeService:
    service = KnowledgeService(MarkdownDocumentSource(DOCS_DIR), build_embedder(settings.embedder))
    service.build()
    return service


def build_knowledge_router(service: KnowledgeService) -> Router:
    return Router(
        path="/",
        route_handlers=[KnowledgeController],
        dependencies={"knowledge_service": Provide(lambda: service, sync_to_thread=False)},
    )
