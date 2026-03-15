"""Program strategy — defines how a program allocates its budget."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.programs.program_state import ProgramState


@dataclass
class AllocationDecision:
    """Decision about which program gets the next planning cycle."""
    program_id: str = ""
    action: str = ""
    budget_allocated: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "action": self.action,
            "budget_allocated": self.budget_allocated,
            "rationale": self.rationale,
        }


class ProgramStrategy:
    """Decides how to allocate resources across programs."""

    def allocate(self, programs: list[ProgramState]) -> AllocationDecision | None:
        """Select the program that should get the next planning cycle.

        Prefers programs with:
            - Lower progress (more work needed)
            - Higher remaining budget
            - Active status
        """
        active = [p for p in programs if p.status == "active" and p.budget_remaining > 0]
        if not active:
            return None

        # Simple heuristic: lowest progress with budget
        best = min(active, key=lambda p: p.progress)
        return AllocationDecision(
            program_id=best.program_id,
            action="plan_next",
            budget_allocated=min(10.0, best.budget_remaining),
            rationale=f"Program '{best.name}' has lowest progress ({best.progress:.1%})",
        )
