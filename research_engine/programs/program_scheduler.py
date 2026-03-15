"""Program scheduler — schedules work across research programs."""
from __future__ import annotations

from typing import Any

from research_engine.programs.program_state import ProgramState
from research_engine.programs.program_strategy import ProgramStrategy, AllocationDecision


class ProgramScheduler:
    """Schedules planning cycles across multiple research programs."""

    def __init__(self, strategy: ProgramStrategy | None = None) -> None:
        self._strategy = strategy or ProgramStrategy()
        self._programs: dict[str, ProgramState] = {}

    def register_program(self, program: ProgramState) -> None:
        self._programs[program.program_id] = program

    def get_program(self, program_id: str) -> ProgramState | None:
        return self._programs.get(program_id)

    def next_allocation(self) -> AllocationDecision | None:
        """Determine which program should get the next planning cycle."""
        return self._strategy.allocate(list(self._programs.values()))

    def update_progress(self, program_id: str, progress: float) -> None:
        program = self._programs.get(program_id)
        if program:
            program.progress = progress

    def deduct_budget(self, program_id: str, amount: float) -> None:
        program = self._programs.get(program_id)
        if program:
            program.budget_remaining = max(0, program.budget_remaining - amount)

    @property
    def active_programs(self) -> list[ProgramState]:
        return [p for p in self._programs.values() if p.status == "active"]
