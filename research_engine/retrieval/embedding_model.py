"""Embedding model interface for vector similarity."""
from __future__ import annotations
import hashlib


class EmbeddingModel:
    """Simple hash-based embedding model (placeholder for real embeddings)."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-embedding from text."""
        h = hashlib.sha256(text.encode()).hexdigest()
        values: list[float] = []
        for i in range(0, min(len(h), self.dim * 2), 2):
            values.append(int(h[i:i+2], 16) / 255.0)
        while len(values) < self.dim:
            values.append(0.0)
        return values[:self.dim]

    def similarity(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
