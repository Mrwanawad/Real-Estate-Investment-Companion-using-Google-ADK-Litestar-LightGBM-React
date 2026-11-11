from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    language: str
    source: str
    topic: str
    body: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    language: str
    source: str
    text: str


@dataclass(frozen=True)
class Citation:
    """What the companion and the report quote when an answer relies on a document."""

    doc_id: str
    title: str
    chunk_id: str
    snippet: str
    source: str

    @classmethod
    def from_hit(cls, hit: dict, max_chars: int = 240) -> "Citation":
        text = " ".join(str(hit["text"]).split())
        snippet = text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"
        return cls(
            doc_id=hit["doc_id"],
            title=hit["title"],
            chunk_id=hit["chunk_id"],
            snippet=snippet,
            source=hit["source"],
        )
