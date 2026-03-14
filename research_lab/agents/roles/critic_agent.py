"""Critic agent for evaluating reasoning quality."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CritiqueResult:
    """Result of critiquing a reasoning chain or result."""
    target_id: str = ""
    issues: list[str] = field(default_factory=list)
    score: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "issues": list(self.issues),
            "score": self.score,
            "recommendation": self.recommendation,
        }


class CriticAgent:
    """Evaluates and critiques reasoning chains and results."""

    def critique_claim(self, claim: dict) -> CritiqueResult:
        """Evaluate a single claim for quality issues."""
        issues: list[str] = []
        score = 1.0

        if not claim.get("text", claim.get("content", "")):
            issues.append("Empty claim content")
            score -= 0.5

        confidence = claim.get("confidence", 0)
        if confidence < 0.3:
            issues.append(f"Low confidence: {confidence}")
            score -= 0.3

        if not claim.get("source", claim.get("source_passage", "")):
            issues.append("No source attribution")
            score -= 0.2

        score = max(0.0, score)
        recommendation = "accept" if score >= 0.7 else ("revise" if score >= 0.4 else "reject")
        return CritiqueResult(
            target_id=claim.get("id", ""),
            issues=issues,
            score=score,
            recommendation=recommendation,
        )

    def critique_experiment(self, result: dict) -> CritiqueResult:
        """Evaluate experiment results for validity."""
        issues: list[str] = []
        score = 1.0

        if not result.get("metrics"):
            issues.append("No metrics reported")
            score -= 0.4

        if result.get("confidence", 0) < 0.5:
            issues.append("Low confidence in results")
            score -= 0.3

        score = max(0.0, score)
        return CritiqueResult(
            target_id=result.get("experiment_id", ""),
            issues=issues,
            score=score,
            recommendation="accept" if score >= 0.6 else "repeat",
        )
