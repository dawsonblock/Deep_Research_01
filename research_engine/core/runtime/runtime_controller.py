"""Runtime controller — high-level orchestrator for the research loop within the
research_engine runtime.

Owns the entire cycle:
    task → planner → operator execution → artifact creation →
    evaluation → graph update → replanning → new tasks

Within the research_engine layer, research-loop execution is expected to
route through this controller to prevent fragmentation across backend,
research_engine, and research_lab, while still allowing lower-level
executors (such as the canonical runtime executor) to be used where
appropriate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from research_engine.core.tasks.task import Task, TaskStatus
from research_engine.core.events.event_bus import EventBus
from research_engine.analysis.experiment_evaluator import ExperimentEvaluator, EvaluationResult
from research_engine.planner.replanner import Replanner, ReplanDecision


@dataclass
class RuntimeResult:
    """Outcome of running a single task through the full loop.

    Attributes:
        task: The task that was executed.
        artifacts: Artifacts produced by the operator.
        evaluation: Evaluation result from the experiment evaluator.
        replan: Replanning decision (may include follow-up tasks).
        errors: Errors that occurred during execution and should be treated as failures.
        warnings: Non-fatal issues encountered during execution (e.g., graph update problems).
    """

    task: Task | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    evaluation: EvaluationResult | None = None
    replan: ReplanDecision | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    evaluation: EvaluationResult | None = None
    replan: ReplanDecision | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors and self.task is not None and self.task.status == TaskStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict() if self.task else None,
            "artifacts": list(self.artifacts),
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "replan": self.replan.to_dict() if self.replan else None,
            "errors": list(self.errors),
            "success": self.success,
        }


class RuntimeController:
    """Unified execution authority for the research runtime.

    Wires together:
        * An **executor** — callable mapping ``(task_dict) -> list[artifact_dicts]``
        * An **evaluator** — :class:`ExperimentEvaluator`
        * A **replanner** — :class:`Replanner`
        * A **graph_updater** — optional callback ``(task_dict, artifacts, evaluation_dict) -> None``
        * An **event_bus** — :class:`EventBus` for observability

    Usage::

        controller = RuntimeController(executor=my_executor_fn)
        result = controller.run_task(task)
    """

    def __init__(
        self,
        executor: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
        evaluator: ExperimentEvaluator | None = None,
        replanner: Replanner | None = None,
        graph_updater: Callable[[dict[str, Any], list[dict[str, Any]], dict[str, Any]], None] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._executor = executor or _noop_executor
        self._evaluator = evaluator or ExperimentEvaluator()
        self._replanner = replanner or Replanner()
        self._graph_updater = graph_updater
        self._event_bus = event_bus or EventBus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_task(self, task: Task) -> RuntimeResult:
        """Execute the full research loop for a single :class:`Task`.

        Steps:
            1. Mark task running + emit event.
            2. Execute via the executor callable.
            3. Evaluate artifacts.
            4. Update graph (if updater provided).
            5. Replan based on evaluation score.
            6. Mark task completed / failed + emit events.

        Returns:
            :class:`RuntimeResult` with all outputs and decisions.
        """
        result = RuntimeResult(task=task)

        # 1. Mark running
        task.mark_running()
        self._event_bus.emit("task.started", {"task_id": task.task_id})

        # 2. Execute
        try:
            artifacts = self._executor(task.to_dict())
            result.artifacts = artifacts
            self._event_bus.emit(
                "operator.executed",
                {"task_id": task.task_id, "artifact_count": len(artifacts)},
            )
        except Exception as exc:
            result.errors.append(str(exc))
            task.mark_failed()
            self._event_bus.emit(
                "task.failed",
                {"task_id": task.task_id, "error": str(exc)},
            )
            return result

        # 3. Evaluate
        evaluation = self._evaluator.evaluate(task.to_dict(), artifacts)
        result.evaluation = evaluation
        self._event_bus.emit(
            "evaluation.completed",
            {"task_id": task.task_id, "score": evaluation.score},
        )

        # 4. Graph update
        if self._graph_updater is not None:
            try:
                self._graph_updater(task.to_dict(), artifacts, evaluation.to_dict())
            except Exception as exc:
                # Treat graph update issues as non-fatal warnings to avoid
                # marking the task as failed while still surfacing the problem.
                result.warnings.append(f"graph_update_error: {exc}")

        # 5. Replan
        replan_decision = self._replanner.replan(task, evaluation.score)
        result.replan = replan_decision
        if replan_decision.new_tasks or replan_decision.retry:
            self._event_bus.emit(
                "replan.triggered",
                {
                    "task_id": task.task_id,
                    "reason": replan_decision.reason,
                    "retry": replan_decision.retry,
                    "new_task_count": len(replan_decision.new_tasks),
                },
            )

        # 6. Finalise task status
        task.mark_completed()
        self._event_bus.emit("task.completed", {"task_id": task.task_id})

        return result

    @property
    def event_bus(self) -> EventBus:
        """Access the underlying event bus for subscriptions."""
        return self._event_bus


# ------------------------------------------------------------------
# Fallback executor
# ------------------------------------------------------------------

def _noop_executor(task_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Default executor that returns no artifacts."""
    return []
