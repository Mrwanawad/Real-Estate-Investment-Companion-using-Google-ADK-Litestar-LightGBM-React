"""Retrieval evaluation on evals/rag_gold.jsonl: bm25-only, vector-only and hybrid.

Uses the hashing embedder (no model download). Metrics are over distinct documents, k=4:
recall@4 is the share of questions with at least one relevant document in the top 4
(a question lists both language versions of a topic as relevant), MRR uses the first one.
Run: .venv/Scripts/python scripts/eval_rag.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reic.bootstrap.knowledge import DOCS_DIR  # noqa: E402
from reic.modules.knowledge.adapters.outbound.hashing_embedder import HashingEmbedder  # noqa: E402
from reic.modules.knowledge.adapters.outbound.markdown_source import (  # noqa: E402
    MarkdownDocumentSource,
)
from reic.modules.knowledge.application.service import KnowledgeService  # noqa: E402

K = 4


def evaluate(service: KnowledgeService, gold: list[dict], mode: str) -> dict:
    hits, reciprocal = 0, 0.0
    for item in gold:
        results = service.search(item["question"], k=K, language=item["language"], mode=mode)
        ranked = [r["doc_id"] for r in results]
        relevant = set(item["relevant"])
        first = next((i for i, d in enumerate(ranked, start=1) if d in relevant), None)
        if first:
            hits += 1
            reciprocal += 1 / first
    n = len(gold)
    return {"recall@4": round(hits / n, 4), "mrr": round(reciprocal / n, 4)}


def main() -> None:
    gold = [
        json.loads(line)
        for line in (ROOT / "evals" / "rag_gold.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    service = KnowledgeService(MarkdownDocumentSource(DOCS_DIR), HashingEmbedder())
    chunks = service.build()
    metrics = {
        "embedder": "hashing-384",
        "questions": len(gold),
        "questions_by_language": {
            lang: sum(1 for g in gold if g["language"] == lang) for lang in ("en", "ar")
        },
        "chunks": chunks,
        "k": K,
        "data": "synthetic corpus in demo_data/docs",
        "results": {mode: evaluate(service, gold, mode) for mode in ("bm25", "vector", "hybrid")},
    }
    out = ROOT / "evals" / "results" / "rag_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
