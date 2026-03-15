"""Belief store — in-memory storage for belief states."""
from __future__ import annotations

from typing import Any

from research_engine.beliefs.belief_model import Belief


class BeliefStore:
    """Stores and retrieves belief states."""

    def __init__(self) -> None:
        self._beliefs: dict[str, Belief] = {}
        self._by_claim: dict[str, str] = {}  # claim_id → belief_id

    def store(self, belief: Belief) -> Belief:
        self._beliefs[belief.belief_id] = belief
        self._by_claim[belief.claim_id] = belief.belief_id
        return belief

    def get(self, belief_id: str) -> Belief | None:
        return self._beliefs.get(belief_id)

    def get_by_claim(self, claim_id: str) -> Belief | None:
        bid = self._by_claim.get(claim_id)
        if bid:
            return self._beliefs.get(bid)
        return None

    def update_confidence(self, claim_id: str, confidence: float) -> Belief | None:
        belief = self.get_by_claim(claim_id)
        if belief:
            belief.confidence = confidence
            import time
            belief.last_updated = time.time()
        return belief

    def all_beliefs(self) -> list[Belief]:
        return list(self._beliefs.values())

    def count(self) -> int:
        return len(self._beliefs)
