import hashlib

import numpy as np

from reic.modules.knowledge.domain.text import normalize, tokenize


class HashingEmbedder:
    """Deterministic character n-gram feature hashing. No model, no network, no cross-lingual
    transfer: it matches spelling, so it is the test and CI embedder."""

    def __init__(self, dims: int = 384, ngrams: tuple[int, ...] = (3, 4)) -> None:
        self.dims = dims
        self._ngrams = ngrams

    def _slot(self, feature: str) -> tuple[int, float]:
        digest = hashlib.md5(feature.encode("utf-8"), usedforsecurity=False).digest()
        value = int.from_bytes(digest[:8], "little")
        return value % self.dims, 1.0 if (value >> 63) & 1 else -1.0

    def _features(self, text: str) -> list[str]:
        features = []
        for token in tokenize(text):
            padded = f"<{token}>"
            features.append(f"w:{token}")
            for n in self._ngrams:
                features.extend(f"{n}:{padded[i : i + n]}" for i in range(len(padded) - n + 1))
        return features

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature in self._features(normalize(text)):
                slot, sign = self._slot(feature)
                out[row, slot] += sign
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out.tolist()
