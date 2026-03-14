"""Worker pool for parallel experiment execution."""
from __future__ import annotations
from dataclasses import dataclass, field

from research_lab.experiments.experiment_spec import ExperimentSpec, ExperimentResult
from research_lab.experiments.experiment_runner import ExperimentRunner


@dataclass
class WorkerResult:
    """Result from a worker execution."""
    worker_id: int
    result: ExperimentResult

    def to_dict(self) -> dict:
        return {"worker_id": self.worker_id, "result": self.result.to_dict()}


class WorkerPool:
    """Pool of workers for executing experiments sequentially (sync fallback)."""

    def __init__(self, runner: ExperimentRunner, max_workers: int = 4) -> None:
        self.runner = runner
        self.max_workers = max_workers
        self._results: list[WorkerResult] = []

    def execute_batch(self, specs: list[ExperimentSpec]) -> list[WorkerResult]:
        """Execute a batch of experiments sequentially."""
        results: list[WorkerResult] = []
        for i, spec in enumerate(specs):
            worker_id = i % self.max_workers
            result = self.runner.run(spec)
            wr = WorkerResult(worker_id=worker_id, result=result)
            results.append(wr)
            self._results.append(wr)
        return results

    def all_results(self) -> list[WorkerResult]:
        return list(self._results)
