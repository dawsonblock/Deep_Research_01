"""In-memory vector index for similarity search."""
from __future__ import annotations
from dataclasses import dataclass, field

from research_engine.retrieval.embedding_model import EmbeddingModel


@dataclass
class IndexEntry:
    """An entry in the vector index."""
    entry_id: str
    text: str
    vector: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class VectorIndex:
    """Simple in-memory vector index using brute-force similarity."""

    def __init__(self, model: EmbeddingModel | None = None) -> None:
        self.model = model or EmbeddingModel()
        self._entries: dict[str, IndexEntry] = {}

    def add(self, entry_id: str, text: str, metadata: dict | None = None) -> None:
        vector = self.model.embed(text)
        self._entries[entry_id] = IndexEntry(
            entry_id=entry_id,
            text=text,
            vector=vector,
            metadata=metadata or {},
        )

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Search for entries most similar to query text."""
        query_vec = self.model.embed(query)
        scored: list[tuple[str, float]] = []
        for entry in self._entries.values():
            sim = self.model.similarity(query_vec, entry.vector)
            scored.append((entry.entry_id, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get(self, entry_id: str) -> IndexEntry | None:
        return self._entries.get(entry_id)

    def count(self) -> int:
        return len(self._entries)
