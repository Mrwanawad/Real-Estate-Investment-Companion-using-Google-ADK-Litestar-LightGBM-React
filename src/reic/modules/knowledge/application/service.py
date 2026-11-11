from reic.modules.knowledge.domain.bm25 import BM25Index
from reic.modules.knowledge.domain.chunker import chunk_document
from reic.modules.knowledge.domain.fusion import reciprocal_rank_fusion
from reic.modules.knowledge.domain.models import Chunk
from reic.modules.knowledge.domain.vector_index import VectorIndex
from reic.modules.knowledge.ports.document_source import DocumentSource
from reic.modules.knowledge.ports.embedder import Embedder

CANDIDATES = 30
LANGUAGE_BOOST = 1.25
MODES = ("hybrid", "bm25", "vector")


class KnowledgeService:
    """Hybrid search (BM25 + embeddings fused with RRF) over the markdown corpus."""

    def __init__(self, source: DocumentSource, embedder: Embedder) -> None:
        self._source = source
        self._embedder = embedder
        self._chunks: list[Chunk] = []
        self._bm25: BM25Index | None = None
        self._vectors: VectorIndex | None = None

    def build(self) -> int:
        """Chunk and index the corpus. Returns the number of chunks."""
        self._chunks = [c for d in self._source.load() for c in chunk_document(d)]
        texts = [c.text for c in self._chunks]
        self._bm25 = BM25Index(texts)
        self._vectors = VectorIndex(self._embedder.embed(texts) if texts else [])
        return len(self._chunks)

    def search(
        self, query: str, k: int = 4, language: str | None = None, mode: str = "hybrid"
    ) -> list[dict]:
        """Best chunk per document, best first. `language` boosts that language but never
        excludes the others, so an Arabic question can still cite an English document."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if self._bm25 is None or self._vectors is None:
            self.build()
        assert self._bm25 is not None and self._vectors is not None
        if not query.strip() or not self._chunks:
            return []

        rankings: list[list[int]] = []
        if mode in ("hybrid", "bm25"):
            rankings.append(self._bm25.rank(query, CANDIDATES))
        if mode in ("hybrid", "vector"):
            query_vector = self._embedder.embed([query])[0]
            rankings.append(self._vectors.rank(query_vector, CANDIDATES))
        fused = reciprocal_rank_fusion(rankings)
        if language:
            for i in fused:
                if self._chunks[i].language == language:
                    fused[i] *= LANGUAGE_BOOST

        hits: list[dict] = []
        seen: set[str] = set()
        for i in sorted(fused, key=lambda i: (-fused[i], i)):
            chunk = self._chunks[i]
            if chunk.doc_id in seen:
                continue
            seen.add(chunk.doc_id)
            hits.append(
                {
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "language": chunk.language,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "score": round(fused[i], 6),
                    "source": chunk.source,
                }
            )
            if len(hits) == k:
                break
        return hits
