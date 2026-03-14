"""Episodic memory for tracking research events and runs."""
from __future__ import annotations
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Episode:
    """A recorded research episode."""
    episode_id: str = ""
    event_type: str = ""
    description: str = ""
    data: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.episode_id:
            self.episode_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "event_type": self.event_type,
            "description": self.description,
            "data": dict(self.data),
            "timestamp": self.timestamp,
        }


class EpisodicMemory:
    """Stores research episodes chronologically."""

    def __init__(self) -> None:
        self._episodes: list[Episode] = []

    def record(self, event_type: str, description: str = "", data: dict | None = None) -> Episode:
        ep = Episode(event_type=event_type, description=description, data=data or {})
        self._episodes.append(ep)
        return ep

    def get_by_type(self, event_type: str) -> list[Episode]:
        return [e for e in self._episodes if e.event_type == event_type]

    def recent(self, n: int = 10) -> list[Episode]:
        return self._episodes[-n:]

    def all_episodes(self) -> list[Episode]:
        return list(self._episodes)

    def count(self) -> int:
        return len(self._episodes)
