import numpy as np


class VectorIndex:
    """In-memory cosine index. Vectors are L2-normalised on the way in."""

    def __init__(self, vectors: list[list[float]]) -> None:
        matrix = np.asarray(vectors, dtype=np.float32).reshape(len(vectors), -1)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self._matrix = matrix / np.where(norms == 0, 1.0, norms)

    def scores(self, query_vector: list[float]) -> list[float]:
        q = np.asarray(query_vector, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm == 0 or self._matrix.size == 0:
            return [0.0] * len(self._matrix)
        return (self._matrix @ (q / norm)).tolist()

    def rank(self, query_vector: list[float], limit: int = 20) -> list[int]:
        scores = self.scores(query_vector)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [i for i in order[:limit] if scores[i] > 0]
