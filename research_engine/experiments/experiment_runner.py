"""Runs individual experiments."""
from __future__ import annotations
from typing import Callable

from research_engine.experiments.experiment_spec import ExperimentSpec, ExperimentResult


class ExperimentRunner:
    """Executes a single experiment spec."""

    def __init__(self) -> None:
        self._executors: dict[str, Callable] = {}

    def register_executor(self, name: str, fn: Callable) -> None:
        """Register an executor function for a type of experiment."""
        self._executors[name] = fn

    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        """Run an experiment from its spec."""
        executor_name = spec.config.get("executor", "default")
        executor = self._executors.get(executor_name)

        if executor is None:
            return ExperimentResult(
                spec_id=spec.spec_id,
                success=False,
                error=f"No executor registered for '{executor_name}'",
            )

        try:
            result_data = executor(spec)
            return ExperimentResult(
                spec_id=spec.spec_id,
                success=True,
                metrics=result_data.get("metrics", {}),
                confidence=result_data.get("confidence", 0.0),
            )
        except Exception as exc:
            return ExperimentResult(
                spec_id=spec.spec_id,
                success=False,
                error=str(exc),
            )
