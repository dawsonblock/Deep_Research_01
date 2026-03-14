"""Search engine combining vector and keyword search."""
from __future__ import annotations

from research_lab.retrieval.vector_index import VectorIndex


class SearchEngine:
    """Evidence search engine using vector similarity."""

    def __init__(self, index: VectorIndex | None = None) -> None:
        self.index = index or VectorIndex()

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        self.index.add(doc_id, text, metadata)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for relevant documents."""
        results = self.index.search(query, top_k=top_k)
        output: list[dict] = []
        for entry_id, score in results:
            entry = self.index.get(entry_id)
            output.append({
                "id": entry_id,
                "score": score,
                "text": entry.text if entry else "",
                "metadata": entry.metadata if entry else {},
            })
        return output
