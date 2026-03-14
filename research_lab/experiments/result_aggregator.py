"""Aggregates results from multiple experiment runs."""
from __future__ import annotations

from research_lab.experiments.experiment_spec import ExperimentResult


class ResultAggregator:
    """Collects and summarizes experiment results."""

    def __init__(self) -> None:
        self._results: list[ExperimentResult] = []

    def add(self, result: ExperimentResult) -> None:
        self._results.append(result)

    def add_batch(self, results: list[ExperimentResult]) -> None:
        self._results.extend(results)

    def success_rate(self) -> float:
        if not self._results:
            return 0.0
        successes = sum(1 for r in self._results if r.success)
        return successes / len(self._results)

    def average_confidence(self) -> float:
        if not self._results:
            return 0.0
        return sum(r.confidence for r in self._results) / len(self._results)

    def failed_experiments(self) -> list[ExperimentResult]:
        return [r for r in self._results if not r.success]

    def summary(self) -> dict:
        return {
            "total": len(self._results),
            "success_rate": self.success_rate(),
            "average_confidence": self.average_confidence(),
            "failed_count": len(self.failed_experiments()),
        }

    def all_results(self) -> list[ExperimentResult]:
        return list(self._results)
