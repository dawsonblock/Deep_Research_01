"""Evidence agent — handles evidence retrieval and ranking."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class EvidenceAgent(AgentBase):
    """Retrieves and ranks evidence for claims.

    Handles:
    - Evidence retrieval
    - Evidence ranking
    - Unsupported-claim review

    Does NOT mutate the graph directly.
    """

    HANDLED_TASKS = {"search_evidence", "rank_evidence", "review_unsupported"}

    def __init__(self, agent_id: str = "evidence_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="evidence")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.EXECUTION_REQUEST,
            task_type="search_evidence",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "search_evidence":
            return self._search_evidence(request.payload)
        if request.task_type == "rank_evidence":
            return self._rank_evidence(request.payload)
        if request.task_type == "review_unsupported":
            return self._review_unsupported(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _search_evidence(self, payload: dict[str, Any]) -> AgentResponse:
        claim_id = payload.get("claim_id", "")
        query = payload.get("query", "")
        if not query and not claim_id:
            return AgentResponse(
                source_agent=self.agent_id,
                task_type="search_evidence",
                success=False,
                errors=["No claim_id or query provided"],
            )
        # Placeholder: in production this would search actual evidence stores
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="search_evidence",
            success=True,
            result={
                "claim_id": claim_id,
                "query": query,
                "evidence_items": [],
                "search_performed": True,
            },
        )

    def _rank_evidence(self, payload: dict[str, Any]) -> AgentResponse:
        evidence_items = payload.get("evidence_items", [])
        ranked = sorted(
            evidence_items,
            key=lambda e: e.get("strength", 0.0),
            reverse=True,
        )
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="rank_evidence",
            success=True,
            result={"ranked_evidence": ranked, "count": len(ranked)},
        )

    def _review_unsupported(self, payload: dict[str, Any]) -> AgentResponse:
        claims = payload.get("claims", [])
        unsupported = [c for c in claims if c.get("evidence_count", 0) == 0]
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="review_unsupported",
            success=True,
            result={
                "unsupported_claims": unsupported,
                "total_reviewed": len(claims),
                "unsupported_count": len(unsupported),
            },
        )
