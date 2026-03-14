"""Tracks and learns from failure patterns."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class FailurePattern:
    """A recorded failure pattern."""
    pattern_id: str = ""
    category: str = ""
    description: str = ""
    occurrences: int = 0
    last_seen: float = 0.0
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category,
            "description": self.description,
            "occurrences": self.occurrences,
            "last_seen": self.last_seen,
        }


class FailurePatternStore:
    """Stores and queries failure patterns for learning."""

    def __init__(self) -> None:
        self._patterns: dict[str, FailurePattern] = {}
        self._counter: int = 0

    def record_failure(
        self,
        category: str,
        description: str,
        context: dict | None = None,
    ) -> FailurePattern:
        """Record a failure, incrementing count if pattern exists."""
        key = f"{category}:{description}"
        if key in self._patterns:
            pattern = self._patterns[key]
            pattern.occurrences += 1
            pattern.last_seen = time.time()
            return pattern

        self._counter += 1
        pattern = FailurePattern(
            pattern_id=f"fp_{self._counter}",
            category=category,
            description=description,
            occurrences=1,
            last_seen=time.time(),
            context=context or {},
        )
        self._patterns[key] = pattern
        return pattern

    def get_frequent(self, min_occurrences: int = 2) -> list[FailurePattern]:
        return [p for p in self._patterns.values() if p.occurrences >= min_occurrences]

    def should_avoid(self, category: str, description: str, threshold: int = 3) -> bool:
        """Check if a pattern has been seen enough times to avoid."""
        key = f"{category}:{description}"
        pattern = self._patterns.get(key)
        return pattern is not None and pattern.occurrences >= threshold

    def all_patterns(self) -> list[FailurePattern]:
        return list(self._patterns.values())
