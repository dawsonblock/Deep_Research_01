"""Theory agent — handles hypothesis generation and theory revision."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class TheoryAgent(AgentBase):
    """Generates hypotheses and proposes theory revisions.

    Handles:
    - Contradiction clustering
    - Hypothesis generation
    - Theory revision proposals
    """

    HANDLED_TASKS = {"generate_hypothesis", "cluster_contradictions", "revise_theory"}

    def __init__(self, agent_id: str = "theory_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="theory")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.ARTIFACT_PROPOSAL,
            task_type="generate_hypothesis",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "generate_hypothesis":
            return self._generate_hypothesis(request.payload)
        if request.task_type == "cluster_contradictions":
            return self._cluster_contradictions(request.payload)
        if request.task_type == "revise_theory":
            return self._revise_theory(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _generate_hypothesis(self, payload: dict[str, Any]) -> AgentResponse:
        claims = payload.get("claims", [])
        context = payload.get("context", "")
        if not claims:
            return AgentResponse(
                source_agent=self.agent_id,
                task_type="generate_hypothesis",
                success=True,
                result={"hypothesis": "No claims available", "confidence": 0.0},
            )
        texts = [c.get("text", c.get("content", "")) for c in claims[:3]]
        hypothesis = f"Based on {len(claims)} claims in context '{context}': " + "; ".join(texts)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="generate_hypothesis",
            success=True,
            result={"hypothesis": hypothesis, "confidence": 0.5, "claim_count": len(claims)},
        )

    def _cluster_contradictions(self, payload: dict[str, Any]) -> AgentResponse:
        contradictions = payload.get("contradictions", [])
        clusters: list[list[dict[str, Any]]] = []
        # Simple grouping: each contradiction becomes its own cluster
        for c in contradictions:
            clusters.append([c])
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="cluster_contradictions",
            success=True,
            result={"clusters": clusters, "cluster_count": len(clusters)},
        )

    def _revise_theory(self, payload: dict[str, Any]) -> AgentResponse:
        theory = payload.get("theory", {})
        new_evidence = payload.get("new_evidence", [])
        revision = {
            "original_theory": theory.get("hypothesis", ""),
            "new_evidence_count": len(new_evidence),
            "revised": True,
            "revision_note": f"Revised with {len(new_evidence)} new evidence items",
        }
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="revise_theory",
            success=True,
            result=revision,
        )
