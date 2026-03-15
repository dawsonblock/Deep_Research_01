"""Replanner — adaptive replanning based on evaluation scores.

After the evaluator scores a task's artifacts, the replanner decides
whether the system should collect more evidence, refine operators, or
move on to the next research objective.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.core.tasks.task import Task


@dataclass
class ReplanDecision:
    """Output of a replanning step.

    Attributes:
        new_tasks: Additional tasks to inject into the task graph.
        reason: Human-readable explanation of the decision.
        retry: Whether the original task should be retried.
    """

    new_tasks: list[Task] = field(default_factory=list)
    reason: str = ""
    retry: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_tasks": [t.to_dict() for t in self.new_tasks],
            "reason": self.reason,
            "retry": self.retry,
        }


class Replanner:
    """Generates follow-up tasks when evaluation scores are unsatisfactory.

    Thresholds:
        * score < ``retry_threshold`` → retry the same task.
        * score < ``expand_threshold`` → add supplementary tasks.
        * score >= ``expand_threshold`` → accept and move on.
    """

    def __init__(
        self,
        retry_threshold: float = 0.3,
        expand_threshold: float = 0.6,
    ) -> None:
        self.retry_threshold = retry_threshold
        self.expand_threshold = expand_threshold

    def replan(
        self,
        task: Task,
        score: float,
    ) -> ReplanDecision:
        """Decide whether to accept, retry, or expand.

        Args:
            task: The original task.
            score: Composite evaluation score in [0, 1].

        Returns:
            :class:`ReplanDecision` describing follow-up actions.
        """
        if score < self.retry_threshold:
            return ReplanDecision(
                reason=f"Score {score:.2f} below retry threshold {self.retry_threshold}; retrying task",
                retry=True,
            )

        if score < self.expand_threshold:
            supplementary = Task(
                description=f"Collect more sources for: {task.description}",
                operator="collect_sources",
                inputs={"original_task_id": task.task_id},
                priority=task.priority,
            )
            return ReplanDecision(
                new_tasks=[supplementary],
                reason=f"Score {score:.2f} below expand threshold {self.expand_threshold}; adding supplementary tasks",
            )

        return ReplanDecision(
            reason=f"Score {score:.2f} acceptable; no replanning needed",
        )
