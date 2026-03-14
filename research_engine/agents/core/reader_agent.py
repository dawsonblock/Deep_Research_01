"""Reader agent — handles paper ingestion and claim extraction."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class ReaderAgent(AgentBase):
    """Reads papers and extracts claim candidates.

    Handles:
    - Paper ingestion
    - Passage segmentation
    - Claim candidate extraction

    Results are emitted as typed requests, NOT written to the graph directly.
    """

    HANDLED_TASKS = {"ingest_paper", "extract_claims", "segment_passages"}

    def __init__(self, agent_id: str = "reader_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="reader")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.EXECUTION_REQUEST,
            task_type="extract_claims",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "ingest_paper":
            return self._ingest_paper(request.payload)
        if request.task_type == "extract_claims":
            return self._extract_claims(request.payload)
        if request.task_type == "segment_passages":
            return self._segment_passages(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _ingest_paper(self, payload: dict[str, Any]) -> AgentResponse:
        text = payload.get("text", "")
        source = payload.get("source", "unknown")
        if not text:
            return AgentResponse(
                source_agent=self.agent_id,
                task_type="ingest_paper",
                success=False,
                errors=["No paper text provided"],
            )
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="ingest_paper",
            success=True,
            result={
                "source": source,
                "paragraphs": paragraphs,
                "paragraph_count": len(paragraphs),
            },
        )

    def _extract_claims(self, payload: dict[str, Any]) -> AgentResponse:
        text = payload.get("text", "")
        source = payload.get("source", "unknown")
        if not text:
            return AgentResponse(
                source_agent=self.agent_id,
                task_type="extract_claims",
                success=False,
                errors=["No text provided for claim extraction"],
            )
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
        claims = [
            {"text": s, "source": source, "confidence": 0.5}
            for s in sentences
        ]
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="extract_claims",
            success=True,
            result={"claims": claims, "count": len(claims)},
        )

    def _segment_passages(self, payload: dict[str, Any]) -> AgentResponse:
        text = payload.get("text", "")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        passages = [
            {"passage_id": f"p_{i}", "text": p}
            for i, p in enumerate(paragraphs)
        ]
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="segment_passages",
            success=True,
            result={"passages": passages, "count": len(passages)},
        )
