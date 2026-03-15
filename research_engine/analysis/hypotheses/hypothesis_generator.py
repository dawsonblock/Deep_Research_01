"""Generates hypotheses from conflicts and evidence gaps."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid

from research_engine.analysis.conflicts.conflict_detector import Conflict


@dataclass
class GeneratedHypothesis:
    """A hypothesis generated from analysis."""
    hypothesis_id: str = ""
    text: str = ""
    source_type: str = ""
    source_ids: list[str] = field(default_factory=list)
    template: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            self.hypothesis_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "text": self.text,
            "source_type": self.source_type,
            "source_ids": list(self.source_ids),
            "template": self.template,
            "confidence": self.confidence,
        }


class HypothesisGenerator:
    """Generates hypotheses from conflicts and evidence gaps."""

    def from_conflict(self, conflict: Conflict) -> GeneratedHypothesis:
        """Generate a hypothesis from a detected conflict."""
        return GeneratedHypothesis(
            text=f"The conflict between {conflict.claim_a_id} and {conflict.claim_b_id} may be due to methodological differences",
            source_type="conflict",
            source_ids=[conflict.claim_a_id, conflict.claim_b_id],
            template="method_difference",
            confidence=0.4,
        )

    def from_evidence_gap(self, claim_id: str, description: str = "") -> GeneratedHypothesis:
        """Generate a hypothesis to fill an evidence gap."""
        return GeneratedHypothesis(
            text=f"Additional evidence needed for claim {claim_id}: {description}",
            source_type="evidence_gap",
            source_ids=[claim_id],
            template="evidence_needed",
            confidence=0.3,
        )
