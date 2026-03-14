"""Belief timeline — time-ordered views of how confidence changed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.graph.temporal.version_tracker import VersionTracker


@dataclass
class TimelineEntry:
    """A single point in a confidence timeline."""
    revision_id: str
    version: int
    confidence: float
    cause: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "version": self.version,
            "confidence": self.confidence,
            "cause": self.cause,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class BeliefTimeline:
    """Builds time-ordered views of how confidence changed."""

    def __init__(self, tracker: VersionTracker) -> None:
        self.tracker = tracker

    def timeline_for_claim(self, claim_id: str) -> list[TimelineEntry]:
        """Return ordered confidence history for a claim."""
        return self._build_timeline("claim", claim_id)

    def timeline_for_theory(self, theory_id: str) -> list[TimelineEntry]:
        """Return ordered confidence history for a theory."""
        return self._build_timeline("theory", theory_id)

    def latest_confidence(self, entity_type: str, entity_id: str) -> float | None:
        """Return the latest confidence for any tracked entity, or None if no history."""
        rev = self.tracker.latest_version(entity_type, entity_id)
        if rev is None:
            return None
        return rev.state.get("confidence")

    def _build_timeline(self, entity_type: str, entity_id: str) -> list[TimelineEntry]:
        revisions = self.tracker.revision_history(entity_type, entity_id)
        entries: list[TimelineEntry] = []
        for rev in revisions:
            entries.append(
                TimelineEntry(
                    revision_id=rev.revision_id,
                    version=rev.version,
                    confidence=rev.state.get("confidence", 0.0),
                    cause=rev.cause,
                    timestamp=rev.created_at,
                    metadata=rev.metadata,
                )
            )
        return entries
