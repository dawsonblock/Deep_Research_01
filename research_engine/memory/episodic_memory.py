"""Episodic memory — stores research episodes for reflection.

Ported from research_lab/memory/episodic/episodic_memory.py patterns.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Episode:
    """A single research episode."""
    episode_id: str = ""
    action: str = ""
    outcome: str = ""
    artifacts_produced: list[str] = field(default_factory=list)
    beliefs_changed: list[str] = field(default_factory=list)
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.episode_id:
            self.episode_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "action": self.action,
            "outcome": self.outcome,
            "artifacts_produced": self.artifacts_produced,
            "beliefs_changed": self.beliefs_changed,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class EpisodicMemory:
    """Stores research episodes for reflection and learning."""

    def __init__(self, max_episodes: int = 500) -> None:
        self._episodes: list[Episode] = []
        self._max_episodes = max_episodes

    def record(self, episode: Episode) -> None:
        self._episodes.append(episode)
        if len(self._episodes) > self._max_episodes:
            self._episodes = self._episodes[-self._max_episodes:]

    def recent(self, n: int = 10) -> list[Episode]:
        return self._episodes[-n:]

    def by_action(self, action: str) -> list[Episode]:
        return [e for e in self._episodes if e.action == action]

    def success_rate_for_action(self, action: str) -> float:
        episodes = self.by_action(action)
        if not episodes:
            return 0.0
        successes = sum(1 for e in episodes if e.outcome == "success")
        return successes / len(episodes)

    @property
    def count(self) -> int:
        return len(self._episodes)
