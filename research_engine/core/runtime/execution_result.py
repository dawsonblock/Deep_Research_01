"""Execution result — structured output of a canonical runtime execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """Structured result of executing a node through the canonical runtime.

    Attributes:
        status: One of 'success', 'artifact_invalid', 'postcondition_failed',
                'runtime_error', or 'operator_not_found'.
        run_id: The run identifier from the RunRegistry.
        artifacts: List of artifact dicts produced by the operator.
        graph_events: List of graph mutation events triggered.
        postconditions: Postcondition report dict.
        errors: List of error messages, if any.
    """

    status: str = "pending"
    run_id: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    graph_events: list[dict[str, Any]] = field(default_factory=list)
    postconditions: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "artifacts": self.artifacts,
            "graph_events": self.graph_events,
            "postconditions": self.postconditions,
            "errors": self.errors,
        }
