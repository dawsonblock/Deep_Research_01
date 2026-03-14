"""Theory agent for hypothesis generation and evaluation."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class TheoryProposal:
    """A proposed theory or hypothesis."""
    proposal_id: str = ""
    hypothesis: str = ""
    supporting_claims: list[str] = field(default_factory=list)
    contradicting_claims: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.proposal_id:
            self.proposal_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "hypothesis": self.hypothesis,
            "supporting_claims": list(self.supporting_claims),
            "contradicting_claims": list(self.contradicting_claims),
            "confidence": self.confidence,
        }


class TheoryAgent:
    """Generates and evaluates theoretical hypotheses."""

    def generate_hypothesis(
        self,
        claims: list[dict],
        context: str = "",
    ) -> TheoryProposal:
        """Generate a hypothesis from a set of claims."""
        if not claims:
            return TheoryProposal(hypothesis="No claims available for hypothesis generation")
        
        claim_texts = [c.get("text", c.get("content", "")) for c in claims]
        hypothesis_text = f"Based on {len(claims)} claims in context '{context}': " + "; ".join(claim_texts[:3])
        
        return TheoryProposal(
            hypothesis=hypothesis_text,
            supporting_claims=[c.get("id", "") for c in claims if c.get("polarity", "positive") == "positive"],
            contradicting_claims=[c.get("id", "") for c in claims if c.get("polarity") == "negative"],
            confidence=0.5,
        )

    def evaluate_hypothesis(self, proposal: TheoryProposal) -> dict:
        """Evaluate a hypothesis proposal."""
        support_count = len(proposal.supporting_claims)
        contradict_count = len(proposal.contradicting_claims)
        total = support_count + contradict_count
        score = support_count / total if total > 0 else 0.5
        return {
            "proposal_id": proposal.proposal_id,
            "support_ratio": score,
            "total_evidence": total,
            "recommendation": "investigate" if 0.3 < score < 0.7 else ("accept" if score >= 0.7 else "reject"),
        }
