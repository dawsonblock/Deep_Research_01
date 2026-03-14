"""Autonomous research loop — the main system cycle."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
import time


@dataclass
class LoopState:
    """State of the research loop."""
    cycle: int = 0
    running: bool = False
    last_action: str = ""
    last_cycle_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle,
            "running": self.running,
            "last_action": self.last_action,
            "last_cycle_time": self.last_cycle_time,
        }


class ResearchLoop:
    """Autonomous research loop that continuously drives the research engine.

    The loop follows this cycle:
        ingest new literature → update belief graph → detect contradictions →
        generate hypotheses → schedule experiments → evaluate results →
        critique reasoning → update world model → evolve operators →
        update research agenda
    """

    CYCLE_ACTIONS = [
        "ingest_literature",
        "extract_claims",
        "update_belief_graph",
        "detect_contradictions",
        "generate_hypotheses",
        "design_experiments",
        "execute_experiments",
        "evaluate_results",
        "critique_reasoning",
        "update_knowledge",
        "evolve_operators",
        "update_agenda",
    ]

    def __init__(self, max_cycles: int = 0) -> None:
        self.max_cycles = max_cycles
        self.state = LoopState()
        self._action_handlers: dict[str, Callable] = {}
        self._cycle_log: list[dict] = []

    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a handler function for a loop action."""
        self._action_handlers[action] = handler

    def run_cycle(self) -> dict:
        """Run a single research cycle."""
        self.state.cycle += 1
        self.state.running = True
        cycle_start = time.time()
        results: dict[str, object] = {}

        for action in self.CYCLE_ACTIONS:
            handler = self._action_handlers.get(action)
            if handler:
                try:
                    results[action] = handler()
                except Exception as exc:
                    results[action] = {"error": str(exc)}
            else:
                results[action] = {"skipped": True}
            self.state.last_action = action

        self.state.last_cycle_time = time.time() - cycle_start
        self.state.running = False

        cycle_record = {
            "cycle": self.state.cycle,
            "duration": self.state.last_cycle_time,
            "results": results,
        }
        self._cycle_log.append(cycle_record)
        return cycle_record

    def run(self) -> list[dict]:
        """Run the research loop for max_cycles (0 = 1 cycle for safety)."""
        cycles = self.max_cycles if self.max_cycles > 0 else 1
        results: list[dict] = []
        for _ in range(cycles):
            results.append(self.run_cycle())
        return results

    @property
    def cycle_log(self) -> list[dict]:
        return list(self._cycle_log)
