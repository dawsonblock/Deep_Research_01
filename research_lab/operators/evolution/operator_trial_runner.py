"""Operator trial runner — runs candidate operators on held-out tasks."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TrialResult:
    """Result of a single trial run."""
    trial_id: str
    operator_family: str
    version: str
    task_id: str
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    runtime_seconds: float = 0.0
    error: str | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "operator_family": self.operator_family,
            "version": self.version,
            "task_id": self.task_id,
            "success": self.success,
            "runtime_seconds": self.runtime_seconds,
            "error": self.error,
            "created_at": self.created_at,
        }


@dataclass
class TrialSummary:
    """Summary of a batch of trial runs."""
    operator_family: str
    version: str
    total_tasks: int = 0
    successes: int = 0
    failures: int = 0
    avg_runtime: float = 0.0
    results: list[TrialResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_tasks if self.total_tasks > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_family": self.operator_family,
            "version": self.version,
            "total_tasks": self.total_tasks,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": self.success_rate,
            "avg_runtime": self.avg_runtime,
        }


class OperatorTrialRunner:
    """Runs candidate operators on held-out benchmark tasks."""

    def __init__(self) -> None:
        self._trial_history: list[TrialResult] = []

    def run_trial(
        self,
        operator_family: str,
        version: str,
        operator_callable: Callable[..., dict[str, Any]],
        benchmark_tasks: list[dict[str, Any]],
    ) -> TrialSummary:
        """Run a candidate operator on a set of benchmark tasks."""
        results: list[TrialResult] = []
        total_runtime = 0.0

        for task in benchmark_tasks:
            task_id = task.get("task_id", uuid.uuid4().hex[:8])
            start = time.time()
            try:
                output = operator_callable(task)
                elapsed = time.time() - start
                result = TrialResult(
                    trial_id=uuid.uuid4().hex,
                    operator_family=operator_family,
                    version=version,
                    task_id=task_id,
                    success=True,
                    output=output,
                    runtime_seconds=elapsed,
                    created_at=time.time(),
                )
            except Exception as exc:
                elapsed = time.time() - start
                result = TrialResult(
                    trial_id=uuid.uuid4().hex,
                    operator_family=operator_family,
                    version=version,
                    task_id=task_id,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                    runtime_seconds=elapsed,
                    created_at=time.time(),
                )
            results.append(result)
            total_runtime += elapsed

        self._trial_history.extend(results)

        successes = sum(1 for r in results if r.success)
        return TrialSummary(
            operator_family=operator_family,
            version=version,
            total_tasks=len(benchmark_tasks),
            successes=successes,
            failures=len(benchmark_tasks) - successes,
            avg_runtime=total_runtime / len(benchmark_tasks) if benchmark_tasks else 0.0,
            results=results,
        )

    def record_trial_results(self, summary: TrialSummary) -> None:
        """Explicitly store trial results (already recorded in run_trial, but allows external injection)."""
        for result in summary.results:
            if result not in self._trial_history:
                self._trial_history.append(result)

    @property
    def trial_history(self) -> list[TrialResult]:
        return list(self._trial_history)
