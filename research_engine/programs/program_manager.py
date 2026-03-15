"""Program manager — top-level API for managing research programs."""
from __future__ import annotations

from typing import Any

from research_engine.programs.program_state import ProgramState
from research_engine.programs.program_scheduler import ProgramScheduler
from research_engine.programs.program_strategy import ProgramStrategy, AllocationDecision


class ProgramManager:
    """Top-level API for managing research programs.

    Usage::

        manager = ProgramManager()
        pid = manager.create_program("NLP Research", objectives=["Improve F1"])
        allocation = manager.next()
    """

    def __init__(self) -> None:
        self._scheduler = ProgramScheduler()

    def create_program(
        self,
        name: str,
        objectives: list[str] | None = None,
        budget: float = 100.0,
    ) -> str:
        """Create a new research program. Returns program_id."""
        program = ProgramState(
            name=name,
            objectives=objectives or [],
            budget_remaining=budget,
        )
        self._scheduler.register_program(program)
        return program.program_id

    def get_program(self, program_id: str) -> ProgramState | None:
        return self._scheduler.get_program(program_id)

    def next(self) -> AllocationDecision | None:
        """Get the next allocation decision."""
        return self._scheduler.next_allocation()

    def record_progress(self, program_id: str, progress: float) -> None:
        self._scheduler.update_progress(program_id, progress)

    def record_cost(self, program_id: str, cost: float) -> None:
        self._scheduler.deduct_budget(program_id, cost)

    @property
    def active_programs(self) -> list[ProgramState]:
        return self._scheduler.active_programs
