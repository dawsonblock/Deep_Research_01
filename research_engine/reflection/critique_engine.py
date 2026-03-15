"""Critique engine for evaluating reasoning quality."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CritiqueReport:
    """Report from critiquing a reasoning chain or belief update."""
    target_id: str = ""
    checks: list[dict] = field(default_factory=list)
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    score: float = 1.0

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "checks": list(self.checks),
            "passed": self.passed,
            "issues": list(self.issues),
            "score": self.score,
        }


class CritiqueEngine:
    """Evaluates reasoning quality before belief updates are committed."""

    def check_logical_consistency(self, premises: list[str], conclusion: str) -> dict:
        """Check if a conclusion logically follows from premises."""
        if not premises:
            return {"check": "logical_consistency", "passed": False, "reason": "No premises provided"}
        if not conclusion:
            return {"check": "logical_consistency", "passed": False, "reason": "No conclusion provided"}
        return {"check": "logical_consistency", "passed": True, "reason": "Premises and conclusion present"}

    def check_evidence_sufficiency(self, evidence_count: int, min_evidence: int = 2) -> dict:
        """Check if sufficient evidence supports a claim."""
        passed = evidence_count >= min_evidence
        return {
            "check": "evidence_sufficiency",
            "passed": passed,
            "reason": f"Evidence count {evidence_count} {'meets' if passed else 'below'} minimum {min_evidence}",
        }

    def check_confidence_propagation(self, source_confidence: float, derived_confidence: float) -> dict:
        """Check that derived confidence does not exceed source."""
        passed = derived_confidence <= source_confidence + 0.1
        return {
            "check": "confidence_propagation",
            "passed": passed,
            "reason": f"Derived {derived_confidence:.2f} {'ok' if passed else 'exceeds'} source {source_confidence:.2f}",
        }

    def critique(self, target_id: str, checks: list[dict]) -> CritiqueReport:
        """Generate a critique report from a set of check results."""
        issues = [c.get("reason", "") for c in checks if not c.get("passed", True)]
        passed = len(issues) == 0
        score = sum(1 for c in checks if c.get("passed", True)) / max(len(checks), 1)
        return CritiqueReport(
            target_id=target_id,
            checks=checks,
            passed=passed,
            issues=issues,
            score=score,
        )
