"""Research topic lifecycle management."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class ResearchTopic:
    """A research topic tracked by the system."""
    name: str
    topic_id: str = ""
    priority: float = 0.0
    uncertainty: float = 0.0
    active_hypotheses: list[str] = field(default_factory=list)
    status: str = "active"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.topic_id:
            self.topic_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "priority": self.priority,
            "uncertainty": self.uncertainty,
            "active_hypotheses": list(self.active_hypotheses),
            "status": self.status,
            "metadata": dict(self.metadata),
        }


class TopicManager:
    """Manages the lifecycle of research topics."""

    def __init__(self) -> None:
        self._topics: dict[str, ResearchTopic] = {}

    def add_topic(self, topic: ResearchTopic) -> ResearchTopic:
        self._topics[topic.topic_id] = topic
        return topic

    def create_topic(self, name: str, priority: float = 0.0, uncertainty: float = 0.0) -> ResearchTopic:
        topic = ResearchTopic(name=name, priority=priority, uncertainty=uncertainty)
        return self.add_topic(topic)

    def get_topic(self, topic_id: str) -> ResearchTopic | None:
        return self._topics.get(topic_id)

    def remove_topic(self, topic_id: str) -> None:
        self._topics.pop(topic_id, None)

    def active_topics(self) -> list[ResearchTopic]:
        return [t for t in self._topics.values() if t.status == "active"]

    def all_topics(self) -> list[ResearchTopic]:
        return list(self._topics.values())

    def update_priority(self, topic_id: str, priority: float) -> None:
        topic = self._topics.get(topic_id)
        if topic:
            topic.priority = priority

    def archive_topic(self, topic_id: str) -> None:
        topic = self._topics.get(topic_id)
        if topic:
            topic.status = "archived"
