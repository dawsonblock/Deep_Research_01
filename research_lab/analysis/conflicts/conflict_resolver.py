"""Resolves conflicts between claims."""
from __future__ import annotations
from dataclasses import dataclass

from research_lab.analysis.conflicts.conflict_detector import Conflict


@dataclass
class Resolution:
    """Resolution of a conflict."""
    conflict: Conflict
    action: str = ""
    winning_claim_id: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "conflict": self.conflict.to_dict(),
            "action": self.action,
            "winning_claim_id": self.winning_claim_id,
            "reason": self.reason,
        }


class ConflictResolver:
    """Resolves detected conflicts using resolution strategies."""

    def resolve_by_confidence(
        self,
        conflict: Conflict,
        claim_a_confidence: float,
        claim_b_confidence: float,
        margin: float = 0.15,
    ) -> Resolution:
        """Resolve by comparing claim confidence levels."""
        diff = abs(claim_a_confidence - claim_b_confidence)
        if diff < margin:
            return Resolution(
                conflict=conflict,
                action="escalate",
                reason=f"Confidence difference {diff:.2f} below margin {margin}",
            )
        if claim_a_confidence > claim_b_confidence:
            return Resolution(
                conflict=conflict,
                action="prefer_a",
                winning_claim_id=conflict.claim_a_id,
                reason=f"Claim A confidence {claim_a_confidence:.2f} > B {claim_b_confidence:.2f}",
            )
        return Resolution(
            conflict=conflict,
            action="prefer_b",
            winning_claim_id=conflict.claim_b_id,
            reason=f"Claim B confidence {claim_b_confidence:.2f} > A {claim_a_confidence:.2f}",
        )
