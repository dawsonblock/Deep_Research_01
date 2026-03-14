"""Planner agent — coordinates research tasks via the agent router."""
from __future__ import annotations

from typing import Any

from research_lab.agents.core.agent_base import AgentBase
from research_lab.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)
from research_lab.planner.research_planner import ResearchPlanner, PlannerState


class PlannerAgent(AgentBase):
    """Plans and routes research tasks.

    The planner reads current graph state, decides the next action,
    and emits typed tasks through the router. It does NOT execute
    tasks directly.
    """

    HANDLED_TASKS = {"plan_next_action", "rank_tasks", "coordinate_agenda"}

    def __init__(self, agent_id: str = "planner_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="planner")
        self.planner = ResearchPlanner()

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.TASK_PROPOSAL,
            task_type="plan_next_action",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "plan_next_action":
            return self._plan_next(request.payload)
        if request.task_type == "rank_tasks":
            return self._rank_tasks(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _plan_next(self, payload: dict[str, Any]) -> AgentResponse:
        state = PlannerState(
            open_hypotheses=payload.get("open_hypotheses", 0),
            unresolved_conflicts=payload.get("unresolved_conflicts", 0),
            untested_claims=payload.get("untested_claims", 0),
            evidence_gaps=payload.get("evidence_gaps", 0),
            pending_experiments=payload.get("pending_experiments", 0),
        )
        action = self.planner.select_action(state)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="plan_next_action",
            success=True,
            result={"action": action, "state": payload},
        )

    def _rank_tasks(self, payload: dict[str, Any]) -> AgentResponse:
        tasks = payload.get("tasks", [])
        ranked = sorted(tasks, key=lambda t: t.get("priority", 0), reverse=True)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="rank_tasks",
            success=True,
            result={"ranked_tasks": ranked},
        )
