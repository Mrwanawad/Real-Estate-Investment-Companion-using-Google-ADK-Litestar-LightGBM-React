from collections.abc import Iterator
from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from reic.bootstrap.knowledge import (
    DOCS_DIR,
    build_embedder,
    build_knowledge_router,
    build_knowledge_service,
)
from reic.modules.knowledge.adapters.outbound.hashing_embedder import HashingEmbedder
from reic.modules.knowledge.adapters.outbound.markdown_source import (
    MarkdownDocumentSource,
    parse_markdown,
)
from reic.modules.knowledge.application.service import KnowledgeService
from reic.modules.knowledge.domain.bm25 import BM25Index
from reic.modules.knowledge.domain.chunker import chunk_document
from reic.modules.knowledge.domain.fusion import reciprocal_rank_fusion
from reic.modules.knowledge.domain.models import Citation, Document
from reic.modules.knowledge.domain.text import normalize, tokenize
from reic.shared.config import Settings


@pytest.fixture(scope="module")
def service() -> KnowledgeService:
    return build_knowledge_service(Settings())


def test_normalize_arabic() -> None:
    assert normalize("المُقَدِّمَة") == normalize("المقدمه")
    assert normalize("مــقــدم") == "مقدم"
    assert normalize("أحمد إبراهيم آمن") == "احمد ابراهيم امن"
    assert normalize("على") == normalize("علي")
    assert normalize("٢٥٪") == "25٪"


def test_tokenize_drops_stopwords_and_article() -> None:
    assert tokenize("The deposits of the unit") == ["deposit", "unit"]
    assert tokenize("القسط الشهري")[0] == "قسط"


def test_chunker_respects_headings_size_and_overlap() -> None:
    para = " ".join(f"word{i}" for i in range(150))
    doc = Document(
        "d", "T", "en", "synthetic", "t", f"# Title\n\n## A\n{para}\n\n## B\nShort text."
    )
    chunks = chunk_document(doc, size=300, overlap=60)
    a = [c for c in chunks if c.text.startswith("A\n")]
    assert len(a) > 1
    assert all(len(c.text) < 420 for c in chunks)
    assert chunks[-1].text == "B\nShort text."
    # overlap: the next chunk starts with words that ended the previous one
    first_words = a[1].text.split("\n", 1)[1].split()[:2]
    assert " ".join(first_words) in a[0].text
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_parse_markdown_front_matter() -> None:
    doc = parse_markdown("---\nid: x\ntitle: Hello\nlanguage: ar\n---\nbody", "fallback")
    assert (doc.id, doc.title, doc.language, doc.body) == ("x", "Hello", "ar", "body")


def test_corpus_is_labelled_synthetic() -> None:
    docs = MarkdownDocumentSource(DOCS_DIR).load()
    assert len(docs) >= 14
    assert {d.language for d in docs} == {"en", "ar"}
    assert sum(d.language == "ar" for d in docs) >= 5
    assert all(d.source == "synthetic" for d in docs)


def test_bm25_ranks_matching_text_first() -> None:
    index = BM25Index(
        [
            "late fee on overdue instalments",
            "mortgage rate and loan to value",
            "maintenance deposit",
        ]
    )
    assert index.rank("mortgage rate")[0] == 1
    assert index.rank("zzz") == []
    arabic = BM25Index(["غرامة التأخير في الأقساط", "رسوم التسجيل في الشهر العقاري"])
    assert arabic.rank("الاقساط المتأخره غرامه")[0] == 0


def test_rrf_rewards_agreement() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 1, 4]])
    order = sorted(fused, key=lambda i: -fused[i])
    assert order[:2] == [1, 3]
    assert fused[1] == pytest.approx(1 / 61 + 1 / 62)


def test_hashing_embedder_is_deterministic_and_normalised() -> None:
    embedder = HashingEmbedder()
    a, b = embedder.embed(["reservation deposit"]), embedder.embed(["reservation deposit"])
    assert a == b
    assert len(a[0]) == 384
    assert sum(x * x for x in a[0]) == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize(
    ("query", "doc_id"),
    [
        (
            "How long is the reservation held and what is the deposit?",
            "reservation-cancellation-en",
        ),
        ("late fee for overdue instalments", "installment-rules-en"),
        ("subsidised mortgage interest rate", "mortgage-options-en"),
        ("maintenance deposit percentage for villas and townhouses", "maintenance-deposit-en"),
        ("ما غرامة التأخر في سداد القسط؟", "installment-rules-ar"),
        ("تعويض التأخير عن تسليم الوحدة بعد فترة السماح", "delivery-delay-ar"),
        ("خطوات التسجيل في الشهر العقاري", "registration-shahr-akary-ar"),
    ],
)
def test_search_finds_right_doc(service: KnowledgeService, query: str, doc_id: str) -> None:
    hits = service.search(query, k=4)
    assert doc_id in [h["doc_id"] for h in hits]
    assert hits[0]["doc_id"] == doc_id


def test_search_result_shape_and_one_chunk_per_doc(service: KnowledgeService) -> None:
    hits = service.search("deposit", k=4)
    assert set(hits[0]) == {"doc_id", "title", "language", "chunk_id", "text", "score", "source"}
    assert hits[0]["source"] == "synthetic"
    assert len({h["doc_id"] for h in hits}) == len(hits)
    assert service.search("   ") == []


def test_language_preference_does_not_exclude(service: KnowledgeService) -> None:
    hits = service.search("reservation deposit", k=6, language="ar")
    languages = [h["language"] for h in hits]
    assert languages[0] == "ar" or "ar" in languages
    assert "en" in languages or len(hits) < 6
    assert service.search("reservation deposit", k=1, language="en")[0]["language"] == "en"


def test_unknown_mode_rejected(service: KnowledgeService) -> None:
    with pytest.raises(ValueError):
        service.search("x", mode="nope")


def test_citation_from_hit(service: KnowledgeService) -> None:
    hit = service.search("late fee", k=1)[0]
    citation = Citation.from_hit(hit, max_chars=50)
    assert citation.doc_id == hit["doc_id"]
    assert len(citation.snippet) <= 50


def test_embedder_selection() -> None:
    assert isinstance(build_embedder("hashing"), HashingEmbedder)


@pytest.fixture
def client(service: KnowledgeService) -> Iterator[TestClient[Any]]:
    with TestClient(app=Litestar([build_knowledge_router(service)])) as test_client:
        yield test_client


def test_api_search(client: TestClient[Any]) -> None:
    response = client.get(
        "/knowledge/search", params={"q": "late fee instalment", "k": 2, "language": "en"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["doc_id"] == "installment-rules-en"


def test_api_validation(client: TestClient[Any]) -> None:
    assert client.get("/knowledge/search").status_code == 400
    assert client.get("/knowledge/search", params={"q": "x", "k": 99}).status_code == 400
    assert client.get("/knowledge/search", params={"q": "x", "language": "fr"}).status_code == 400
