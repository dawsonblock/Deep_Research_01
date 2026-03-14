"""Long-term semantic knowledge archive."""
from __future__ import annotations
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class ArchivedKnowledge:
    """A piece of archived knowledge."""
    archive_id: str = ""
    category: str = ""
    content: str = ""
    confidence: float = 0.0
    source: str = ""
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.archive_id:
            self.archive_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "archive_id": self.archive_id,
            "category": self.category,
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class KnowledgeArchive:
    """Persistent archive of research knowledge."""

    def __init__(self) -> None:
        self._items: dict[str, ArchivedKnowledge] = {}

    def store(
        self,
        category: str,
        content: str,
        confidence: float = 0.0,
        source: str = "",
    ) -> ArchivedKnowledge:
        item = ArchivedKnowledge(
            category=category,
            content=content,
            confidence=confidence,
            source=source,
        )
        self._items[item.archive_id] = item
        return item

    def get(self, archive_id: str) -> ArchivedKnowledge | None:
        return self._items.get(archive_id)

    def search_by_category(self, category: str) -> list[ArchivedKnowledge]:
        return [i for i in self._items.values() if i.category == category]

    def all_items(self) -> list[ArchivedKnowledge]:
        return list(self._items.values())

    def count(self) -> int:
        return len(self._items)
