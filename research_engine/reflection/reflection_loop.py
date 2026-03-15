"""Reflection loop for continuous self-assessment."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class ReflectionEntry:
    """A single reflection cycle entry."""
    cycle_id: int = 0
    timestamp: float = 0.0
    observations: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    quality_score: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "observations": list(self.observations),
            "actions_taken": list(self.actions_taken),
            "quality_score": self.quality_score,
        }


class ReflectionLoop:
    """Manages periodic self-assessment cycles."""

    def __init__(self) -> None:
        self._entries: list[ReflectionEntry] = []
        self._cycle_count: int = 0

    def run_cycle(self, observations: list[str], actions: list[str], score: float = 0.0) -> ReflectionEntry:
        """Record a reflection cycle."""
        self._cycle_count += 1
        entry = ReflectionEntry(
            cycle_id=self._cycle_count,
            observations=observations,
            actions_taken=actions,
            quality_score=score,
        )
        self._entries.append(entry)
        return entry

    def average_quality(self) -> float:
        if not self._entries:
            return 0.0
        return sum(e.quality_score for e in self._entries) / len(self._entries)

    def recent_entries(self, n: int = 5) -> list[ReflectionEntry]:
        return self._entries[-n:]

    def all_entries(self) -> list[ReflectionEntry]:
        return list(self._entries)

    @property
    def cycle_count(self) -> int:
        return self._cycle_count
