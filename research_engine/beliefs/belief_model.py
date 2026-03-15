"""Belief model — defines the structure of a belief state."""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Belief:
    """A single belief with confidence and provenance.

    Attributes:
        belief_id: Unique identifier.
        claim_id: The graph node this belief refers to.
        confidence: Current confidence level (0.0 to 1.0).
        evidence_ids: Evidence nodes that support or weaken this belief.
        last_updated: Timestamp of the most recent update.
        metadata: Arbitrary metadata.
    """
    belief_id: str = ""
    claim_id: str = ""
    confidence: float = 0.5
    evidence_ids: list[str] = field(default_factory=list)
    last_updated: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.belief_id:
            self.belief_id = uuid.uuid4().hex[:12]
        if self.last_updated == 0.0:
            self.last_updated = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "claim_id": self.claim_id,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }
