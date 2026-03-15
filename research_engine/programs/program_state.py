"""Program state — tracks the state of a research program."""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgramState:
    """State of a research program.

    A program owns clusters of objectives, beliefs, experiments,
    progress metrics, and budgets.
    """
    program_id: str = ""
    name: str = ""
    objectives: list[str] = field(default_factory=list)
    belief_ids: list[str] = field(default_factory=list)
    experiment_ids: list[str] = field(default_factory=list)
    progress: float = 0.0
    budget_remaining: float = 100.0
    status: str = "active"
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.program_id:
            self.program_id = uuid.uuid4().hex[:12]
        if self.created_at == 0.0:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "name": self.name,
            "objectives": self.objectives,
            "belief_ids": self.belief_ids,
            "experiment_ids": self.experiment_ids,
            "progress": self.progress,
            "budget_remaining": self.budget_remaining,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
