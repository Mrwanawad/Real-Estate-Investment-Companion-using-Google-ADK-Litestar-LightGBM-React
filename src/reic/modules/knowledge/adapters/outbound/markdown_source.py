from pathlib import Path

from reic.modules.knowledge.domain.models import Document


def parse_markdown(raw: str, fallback_id: str) -> Document:
    """Parse `key: value` front matter between two `---` lines, then the markdown body."""
    meta: dict[str, str] = {}
    body = raw
    lines = raw.splitlines()
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                for line in lines[1:end]:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()
                body = "\n".join(lines[end + 1 :])
                break
    return Document(
        id=meta.get("id", fallback_id),
        title=meta.get("title", fallback_id),
        language=meta.get("language", "en"),
        source=meta.get("source", "synthetic"),
        topic=meta.get("topic", ""),
        body=body.strip(),
    )


class MarkdownDocumentSource:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self) -> list[Document]:
        return [
            parse_markdown(path.read_text(encoding="utf-8"), path.stem)
            for path in sorted(self._directory.glob("*.md"))
        ]
