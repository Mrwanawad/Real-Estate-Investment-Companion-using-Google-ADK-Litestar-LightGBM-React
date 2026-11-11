import math
from collections import Counter

from reic.modules.knowledge.domain.text import tokenize


class BM25Index:
    """Okapi BM25 over a fixed list of texts. Scores are indexed like the input list."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self._k1, self._b = k1, b
        self._tf = [Counter(tokenize(t)) for t in texts]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(texts)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = [t for t in dict.fromkeys(tokenize(query)) if t in self._idf]
        out = []
        for tf, length in zip(self._tf, self._len, strict=True):
            norm = self._k1 * (1 - self._b + self._b * length / self._avg) if self._avg else 0.0
            score = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if f:
                    score += self._idf[term] * f * (self._k1 + 1) / (f + norm)
            out.append(score)
        return out

    def rank(self, query: str, limit: int = 20) -> list[int]:
        """Indices of texts with a positive score, best first."""
        scores = self.scores(query)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [i for i in order[:limit] if scores[i] > 0]
