"""Experiment agent — designs and manages experiments."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class ExperimentAgent(AgentBase):
    """Designs experiments and packages results.

    Handles:
    - Experiment design
    - Benchmark/simulation runs
    - Result packaging
    """

    HANDLED_TASKS = {"design_experiment", "run_benchmark", "package_results"}

    def __init__(self, agent_id: str = "experiment_agent") -> None:
        super().__init__(agent_id=agent_id, agent_type="experiment")

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.HANDLED_TASKS

    def propose(self, task: dict[str, Any]) -> AgentRequest:
        return self.create_request(
            RequestType.EXECUTION_REQUEST,
            task_type="design_experiment",
            payload=task,
        )

    def execute_request(self, request: AgentRequest) -> AgentResponse:
        if request.task_type == "design_experiment":
            return self._design_experiment(request.payload)
        if request.task_type == "run_benchmark":
            return self._run_benchmark(request.payload)
        if request.task_type == "package_results":
            return self._package_results(request.payload)
        return AgentResponse(
            source_agent=self.agent_id,
            task_type=request.task_type,
            success=False,
            errors=[f"Unknown task type: {request.task_type}"],
        )

    def _design_experiment(self, payload: dict[str, Any]) -> AgentResponse:
        hypothesis = payload.get("hypothesis", "")
        variables = payload.get("variables", ["independent_var", "dependent_var"])
        design = {
            "hypothesis": hypothesis,
            "variables": variables,
            "metrics": ["accuracy", "confidence"],
            "status": "designed",
        }
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="design_experiment",
            success=True,
            result=design,
        )

    def _run_benchmark(self, payload: dict[str, Any]) -> AgentResponse:
        benchmark = payload.get("benchmark", "")
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="run_benchmark",
            success=True,
            result={"benchmark": benchmark, "status": "completed", "metrics": {}},
        )

    def _package_results(self, payload: dict[str, Any]) -> AgentResponse:
        results = payload.get("results", {})
        return AgentResponse(
            source_agent=self.agent_id,
            task_type="package_results",
            success=True,
            result={"packaged": True, "result_count": len(results)},
        )
