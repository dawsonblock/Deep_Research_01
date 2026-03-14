"""Topic-level research history tracking."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class TopicHistoryEntry:
    """A historical entry for a research topic."""
    topic_id: str
    event: str
    details: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "event": self.event,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class TopicHistory:
    """Stores chronological history of research topic events."""

    def __init__(self) -> None:
        self._entries: list[TopicHistoryEntry] = []

    def record(self, topic_id: str, event: str, details: str = "") -> TopicHistoryEntry:
        entry = TopicHistoryEntry(topic_id=topic_id, event=event, details=details)
        self._entries.append(entry)
        return entry

    def get_history(self, topic_id: str) -> list[TopicHistoryEntry]:
        return [e for e in self._entries if e.topic_id == topic_id]

    def recent(self, n: int = 10) -> list[TopicHistoryEntry]:
        return sorted(self._entries, key=lambda e: e.timestamp, reverse=True)[:n]

    def all_entries(self) -> list[TopicHistoryEntry]:
        return list(self._entries)
