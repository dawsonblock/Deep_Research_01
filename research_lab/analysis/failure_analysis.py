"""Failure analysis utilities."""
from __future__ import annotations

from research_lab.memory.failures.failure_patterns import FailurePatternStore


class FailureAnalyzer:
    """Analyzes failure patterns to improve future runs."""

    def __init__(self, store: FailurePatternStore | None = None) -> None:
        self.store = store or FailurePatternStore()

    def record_experiment_failure(self, experiment_id: str, error: str) -> None:
        self.store.record_failure(
            category="experiment",
            description=error,
            context={"experiment_id": experiment_id},
        )

    def record_operator_failure(self, operator_name: str, error: str) -> None:
        self.store.record_failure(
            category="operator",
            description=error,
            context={"operator": operator_name},
        )

    def should_skip_experiment(self, error_description: str) -> bool:
        return self.store.should_avoid("experiment", error_description)

    def frequent_failures(self) -> list[dict]:
        return [p.to_dict() for p in self.store.get_frequent(min_occurrences=2)]
