"""Critic agent — evaluates quality and flags issues."""
from __future__ import annotations

from typing import Any

from research_lab.agents.core.agent_base import AgentBase
from research_lab.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class CriticAgent(AgentBase):
    """Critiques artifacts and flags weak support.

    Handles:
    - Weak-support detection
    - Reasoning anomaly checks
    - Error classification
    - Corrective action proposals

    Can reject weak outputs before belief mutation.
    """

    HANDLED_TASKS = {"critique_claim", "critique_experiment", "detect_weak_support", "classify_errors"}

    ACCEPT_THRESHOLD = 0.7
    REVISE_THRESHOLD = 0.4
    EXPERIMENT_ACCEPT_THRESHOLD = 0.6
    LOW_CONFIDENCE_THRESHOLD = 0.3
    WEAK_SUPPORT_CONFIDENCE = 0.4
    WEAK_SUPPORT_MIN_EVIDENCE = 2

    def __init__(self, agent_id: str = "critic_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="critic")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.CRITIQUE_REQUEST,
            task_type="critique_claim",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "critique_claim":
            return self._critique_claim(request.payload)
        if request.task_type == "critique_experiment":
            return self._critique_experiment(request.payload)
        if request.task_type == "detect_weak_support":
            return self._detect_weak_support(request.payload)
        if request.task_type == "classify_errors":
            return self._classify_errors(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _critique_claim(self, payload: dict[str, Any]) -> AgentResponse:
        claim = payload.get("claim", {})
        issues: list[str] = []
        score = 1.0

        text = claim.get("text", claim.get("content", ""))
        if not text:
            issues.append("Empty claim content")
            score -= 0.5

        confidence = claim.get("confidence", 0)
        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            issues.append(f"Low confidence: {confidence}")
            score -= 0.3

        if not claim.get("source", claim.get("source_passage", "")):
            issues.append("No source attribution")
            score -= 0.2

        score = max(0.0, score)
        recommendation = "accept" if score >= self.ACCEPT_THRESHOLD else ("revise" if score >= self.REVISE_THRESHOLD else "reject")

        return AgentResponse(
            source_agent=self.agent_id,
            task_type="critique_claim",
            success=True,
            result={
                "target_id": claim.get("id", ""),
                "issues": issues,
                "score": score,
                "recommendation": recommendation,
            },
        )

    def _critique_experiment(self, payload: dict[str, Any]) -> AgentResponse:
        result = payload.get("result", {})
        issues: list[str] = []
        score = 1.0

        if not result.get("metrics"):
            issues.append("No metrics reported")
            score -= 0.4
        if result.get("confidence", 0) < 0.5:
            issues.append("Low confidence in results")
            score -= 0.3

        score = max(0.0, score)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="critique_experiment",
            success=True,
            result={
                "target_id": result.get("experiment_id", ""),
                "issues": issues,
                "score": score,
                "recommendation": "accept" if score >= self.EXPERIMENT_ACCEPT_THRESHOLD else "repeat",
            },
        )

    def _detect_weak_support(self, payload: dict[str, Any]) -> AgentResponse:
        claims = payload.get("claims", [])
        weak = [
            c for c in claims
            if c.get("confidence", 0) < self.WEAK_SUPPORT_CONFIDENCE or c.get("evidence_count", 0) < self.WEAK_SUPPORT_MIN_EVIDENCE
        ]
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="detect_weak_support",
            success=True,
            result={
                "weak_claims": weak,
                "total_reviewed": len(claims),
                "weak_count": len(weak),
            },
        )

    def _classify_errors(self, payload: dict[str, Any]) -> AgentResponse:
        errors = payload.get("errors", [])
        classified = []
        for err in errors:
            if "confidence" in str(err).lower():
                classified.append({"error": err, "category": "confidence_issue"})
            elif "missing" in str(err).lower():
                classified.append({"error": err, "category": "missing_data"})
            else:
                classified.append({"error": err, "category": "general"})
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="classify_errors",
            success=True,
            result={"classified_errors": classified},
        )
