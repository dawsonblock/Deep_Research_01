"""Belief query — query interface for belief states."""
from __future__ import annotations

from typing import Any

from research_engine.beliefs.belief_store import BeliefStore
from research_engine.beliefs.belief_model import Belief


class BeliefQuery:
    """Query interface for the belief store."""

    def __init__(self, store: BeliefStore) -> None:
        self._store = store

    def low_confidence(self, threshold: float = 0.5) -> list[Belief]:
        """Return beliefs below the confidence threshold."""
        return [b for b in self._store.all_beliefs() if b.confidence < threshold]

    def high_confidence(self, threshold: float = 0.8) -> list[Belief]:
        """Return beliefs above the confidence threshold."""
        return [b for b in self._store.all_beliefs() if b.confidence >= threshold]

    def most_uncertain(self, n: int = 5) -> list[Belief]:
        """Return the n beliefs closest to 0.5 confidence (most uncertain)."""
        beliefs = sorted(
            self._store.all_beliefs(),
            key=lambda b: abs(b.confidence - 0.5),
        )
        return beliefs[:n]

    def recently_updated(self, n: int = 10) -> list[Belief]:
        """Return the n most recently updated beliefs."""
        beliefs = sorted(
            self._store.all_beliefs(),
            key=lambda b: b.last_updated,
            reverse=True,
        )
        return beliefs[:n]
