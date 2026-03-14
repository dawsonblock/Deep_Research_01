"""Synthesis agent — generates reports and summaries."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class SynthesisAgent(AgentBase):
    """Generates summaries, reports, and state-of-field snapshots.

    Handles:
    - Report generation
    - Topic summaries
    - State-of-field snapshots
    """

    HANDLED_TASKS = {"generate_report", "summarize_topic", "snapshot_field"}

    def __init__(self, agent_id: str = "synthesis_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="synthesis")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.ARTIFACT_PROPOSAL,
            task_type="generate_report",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "generate_report":
            return self._generate_report(request.payload)
        if request.task_type == "summarize_topic":
            return self._summarize_topic(request.payload)
        if request.task_type == "snapshot_field":
            return self._snapshot_field(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _generate_report(self, payload: dict[str, Any]) -> AgentResponse:
        claims = payload.get("claims", [])
        title = payload.get("title", "Research Report")
        sections = []
        for i, claim in enumerate(claims):
            text = claim.get("text", claim.get("content", ""))
            conf = claim.get("confidence", 0.0)
            sections.append(f"Finding {i+1}: {text} (confidence: {conf:.2f})")
        report = f"# {title}\n\n" + "\n\n".join(sections) if sections else f"# {title}\n\nNo findings to report."
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="generate_report",
            success=True,
            result={"report": report, "claim_count": len(claims)},
        )

    def _summarize_topic(self, payload: dict[str, Any]) -> AgentResponse:
        topic = payload.get("topic", "unknown")
        claims = payload.get("claims", [])
        summary = f"Topic: {topic}. {len(claims)} claims analyzed."
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="summarize_topic",
            success=True,
            result={"summary": summary, "topic": topic},
        )

    def _snapshot_field(self, payload: dict[str, Any]) -> AgentResponse:
        field_name = payload.get("field", "unknown")
        claims = payload.get("claims", [])
        avg_conf = sum(c.get("confidence", 0) for c in claims) / len(claims) if claims else 0.0
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="snapshot_field",
            success=True,
            result={
                "field": field_name,
                "total_claims": len(claims),
                "average_confidence": round(avg_conf, 3),
            },
        )
