"""Persistent memory for research topic history."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class TopicEvent:
    """A recorded event in topic history."""
    topic_id: str
    event_type: str
    description: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "event_type": self.event_type,
            "description": self.description,
            "timestamp": self.timestamp,
        }


class TopicMemory:
    """Stores historical events for research topics."""

    def __init__(self) -> None:
        self._events: list[TopicEvent] = []

    def record_event(self, topic_id: str, event_type: str, description: str = "") -> TopicEvent:
        event = TopicEvent(topic_id=topic_id, event_type=event_type, description=description)
        self._events.append(event)
        return event

    def get_events(self, topic_id: str) -> list[TopicEvent]:
        return [e for e in self._events if e.topic_id == topic_id]

    def all_events(self) -> list[TopicEvent]:
        return list(self._events)

    def recent_events(self, n: int = 10) -> list[TopicEvent]:
        return sorted(self._events, key=lambda e: e.timestamp, reverse=True)[:n]
