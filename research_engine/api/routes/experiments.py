"""Experiment API routes — delegates to experiment runner."""
from __future__ import annotations

from typing import Any

from research_engine.experiments.experiment_runner import ExperimentRunner
from research_engine.experiments.experiment_spec import ExperimentSpec


_runner = ExperimentRunner()


def run_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    """Run an experiment from a spec payload."""
    spec = ExperimentSpec(
        hypothesis=payload.get("hypothesis", ""),
        variables=payload.get("variables", {}),
        method=payload.get("method", "default"),
    )
    result = _runner.run(spec)
    return result.to_dict()
