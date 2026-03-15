"""Unified task model — every research action is represented as a Task.

Provides a standard schema for all planners, operators, and the runtime
controller to communicate through.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNED = "replanned"


@dataclass
class Task:
    """Standardized research task.

    Attributes:
        task_id: Unique identifier.
        description: Human-readable description of the work.
        operator: Name of the operator that should execute this task.
        inputs: Arbitrary inputs consumed by the operator.
        dependencies: Task IDs that must complete before this task runs.
        status: Current lifecycle state.
        priority: Lower values execute first.
        metadata: Free-form metadata bag.
        created_at: Epoch timestamp of creation.
    """

    description: str = ""
    operator: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = uuid.uuid4().hex[:12]
        if self.created_at == 0.0:
            self.created_at = time.time()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING

    def mark_completed(self) -> None:
        self.status = TaskStatus.COMPLETED

    def mark_failed(self) -> None:
        self.status = TaskStatus.FAILED

    def mark_replanned(self) -> None:
        self.status = TaskStatus.REPLANNED

    @property
    def is_ready(self) -> bool:
        """True when the task has no unresolved dependencies."""
        return self.status == TaskStatus.PENDING and len(self.dependencies) == 0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "operator": self.operator,
            "inputs": dict(self.inputs),
            "dependencies": list(self.dependencies),
            "status": self.status,
            "priority": self.priority,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }
