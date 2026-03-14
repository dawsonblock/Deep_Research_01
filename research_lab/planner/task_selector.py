"""Task selection logic for the research planner."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TaskCandidate:
    """A candidate task for selection."""
    task_id: str
    action: str
    priority: float = 0.0
    estimated_gain: float = 0.0
    context: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.priority + self.estimated_gain

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "action": self.action,
            "priority": self.priority,
            "estimated_gain": self.estimated_gain,
            "score": self.score,
        }


class TaskSelector:
    """Selects the next task to execute from a pool of candidates."""

    def select(self, candidates: list[TaskCandidate]) -> TaskCandidate | None:
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.score)

    def rank(self, candidates: list[TaskCandidate]) -> list[TaskCandidate]:
        return sorted(candidates, key=lambda c: c.score, reverse=True)
