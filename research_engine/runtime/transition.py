"""Transition — defines an atomic runtime transition object.

A transition captures all state changes that happen during a single
execution step: task changes, artifact changes, graph events,
belief updates, and status updates.
"""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transition:
    """Atomic runtime transition capturing all state changes from one execution.

    Attributes:
        transition_id: Unique identifier for this transition.
        run_id: Associated run identifier.
        task_changes: List of task state changes (e.g., status updates).
        artifact_changes: List of artifact mutations (created, updated).
        graph_events: List of graph mutation events.
        belief_updates: List of belief state changes.
        status: Overall transition status ('pending', 'committed', 'rolled_back').
        timestamp: When this transition was created.
    """

    transition_id: str = ""
    run_id: str = ""
    task_changes: list[dict[str, Any]] = field(default_factory=list)
    artifact_changes: list[dict[str, Any]] = field(default_factory=list)
    graph_events: list[dict[str, Any]] = field(default_factory=list)
    belief_updates: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.transition_id:
            self.transition_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def add_task_change(self, task_id: str, change: dict[str, Any]) -> None:
        self.task_changes.append({"task_id": task_id, **change})

    def add_artifact(self, artifact_id: str, artifact_data: dict[str, Any]) -> None:
        self.artifact_changes.append({"artifact_id": artifact_id, **artifact_data})

    def add_graph_event(self, event: dict[str, Any]) -> None:
        self.graph_events.append(event)

    def add_belief_update(self, update: dict[str, Any]) -> None:
        self.belief_updates.append(update)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "run_id": self.run_id,
            "task_changes": self.task_changes,
            "artifact_changes": self.artifact_changes,
            "graph_events": self.graph_events,
            "belief_updates": self.belief_updates,
            "status": self.status,
            "timestamp": self.timestamp,
        }
