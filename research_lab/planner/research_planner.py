"""Research planner that decides the next action based on system state."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PlannerState:
    """Current state visible to the planner."""
    open_hypotheses: int = 0
    unresolved_conflicts: int = 0
    untested_claims: int = 0
    evidence_gaps: int = 0
    pending_experiments: int = 0

    def to_dict(self) -> dict:
        return {
            "open_hypotheses": self.open_hypotheses,
            "unresolved_conflicts": self.unresolved_conflicts,
            "untested_claims": self.untested_claims,
            "evidence_gaps": self.evidence_gaps,
            "pending_experiments": self.pending_experiments,
        }


class ResearchPlanner:
    """Decides the next research action based on system state."""

    ACTIONS = [
        "ingest_literature",
        "extract_claims",
        "search_evidence",
        "detect_conflicts",
        "generate_hypotheses",
        "design_experiment",
        "run_experiment",
        "evaluate_results",
    ]

    def __init__(self) -> None:
        self._rules: list[tuple[callable, str]] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        self._rules.append((lambda s: s.unresolved_conflicts > 0, "detect_conflicts"))
        self._rules.append((lambda s: s.open_hypotheses > 2, "design_experiment"))
        self._rules.append((lambda s: s.evidence_gaps > 0, "search_evidence"))
        self._rules.append((lambda s: s.untested_claims > 5, "extract_claims"))
        self._rules.append((lambda s: True, "ingest_literature"))

    def select_action(self, state: PlannerState) -> str:
        """Select the next action based on current state."""
        for condition, action in self._rules:
            if condition(state):
                return action
        return "ingest_literature"
