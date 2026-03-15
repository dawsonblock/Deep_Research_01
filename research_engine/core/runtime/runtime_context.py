"""Runtime context — carries all state needed for a single node execution."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeContext:
    """Context for a single execution within the canonical runtime.

    Attributes:
        active_node: Identifier of the execution-graph node being executed.
        project_id: Owning project identifier.
        operator_name: Name of the operator to invoke.
        run_id: Unique run identifier (auto-generated if omitted).
        sandbox_policy: Optional sandbox policy name or config dict.
        graph_handle: Optional handle/reference for the graph store.
        state_handle: Optional handle/reference for mutable project state.
        inputs: Resolved input artifacts or data for the operator.
        metadata: Arbitrary key-value metadata for this run.
    """

    active_node: str
    project_id: str
    operator_name: str
    run_id: str = ""
    sandbox_policy: str = "default"
    graph_handle: Any = None
    state_handle: Any = None
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_node": self.active_node,
            "project_id": self.project_id,
            "operator_name": self.operator_name,
            "run_id": self.run_id,
            "sandbox_policy": self.sandbox_policy,
            "metadata": self.metadata,
        }
