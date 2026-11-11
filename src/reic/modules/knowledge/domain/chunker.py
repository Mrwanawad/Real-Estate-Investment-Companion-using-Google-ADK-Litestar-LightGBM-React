import re

from reic.modules.knowledge.domain.models import Chunk, Document

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def _sections(body: str) -> list[tuple[str, list[str]]]:
    """Split a markdown body into (heading, paragraphs) sections."""
    sections: list[tuple[str, list[str]]] = []
    heading, paragraphs, current = "", [], []

    def close_paragraph() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for line in body.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            close_paragraph()
            if paragraphs:
                sections.append((heading, paragraphs.copy()))
                paragraphs.clear()
            heading = match.group(1).strip()
        elif line.strip():
            current.append(line.strip())
        else:
            close_paragraph()
    close_paragraph()
    if paragraphs:
        sections.append((heading, paragraphs))
    return sections


def _words_if_too_long(sentences: list[str], size: int) -> list[str]:
    out: list[str] = []
    for sentence in sentences:
        if len(sentence) <= size:
            out.append(sentence)
            continue
        buf = ""
        for word in sentence.split():
            if buf and len(buf) + 1 + len(word) > size:
                out.append(buf)
                buf = word
            else:
                buf = f"{buf} {word}".strip()
        if buf:
            out.append(buf)
    return out


def _split_long(paragraph: str, size: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?؟])\s+", paragraph)
    pieces: list[str] = []
    buf = ""
    for sentence in _words_if_too_long(sentences, size):
        if buf and len(buf) + 1 + len(sentence) > size:
            pieces.append(buf)
            buf = sentence
        else:
            buf = f"{buf} {sentence}".strip()
    if buf:
        pieces.append(buf)
    return pieces


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return ""
    tail = text[-overlap:]
    cut = tail.find(" ")
    return tail[cut + 1 :] if cut >= 0 else tail


def chunk_document(doc: Document, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """Heading and paragraph aware chunks of about `size` characters.

    A chunk never crosses a heading. Each chunk starts with its heading, and consecutive
    chunks inside one section share about `overlap` characters of context.
    """
    chunks: list[Chunk] = []
    for heading, paragraphs in _sections(doc.body):
        pieces = [p for para in paragraphs for p in _split_long(para, size)]
        groups: list[str] = []
        buf = ""
        for piece in pieces:
            if buf and len(buf) + 1 + len(piece) > size:
                groups.append(buf)
                buf = f"{_tail(buf, overlap)} {piece}".strip()
            else:
                buf = f"{buf} {piece}".strip()
        if buf:
            groups.append(buf)
        for group in groups:
            text = f"{heading}\n{group}" if heading else group
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.id}#{len(chunks)}",
                    doc_id=doc.id,
                    title=doc.title,
                    language=doc.language,
                    source=doc.source,
                    text=text,
                )
            )
    return chunks
