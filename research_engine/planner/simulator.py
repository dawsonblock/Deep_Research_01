"""Plan simulator — evaluates candidate plans before execution.

Inserts a simulation layer between planning and execution so the system
can compare alternative strategies without committing resources.

Pipeline:
    task → planner generates candidates → simulator scores each →
    selector picks best → execution
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """A single step in a plan."""

    operator: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"operator": self.operator, "inputs": dict(self.inputs)}


@dataclass
class Plan:
    """A candidate plan consisting of ordered steps."""

    steps: list[Step] = field(default_factory=list)
    score: float | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "score": self.score,
            "rationale": self.rationale,
        }


# ------------------------------------------------------------------
# Default operator value estimates
# ------------------------------------------------------------------
_DEFAULT_VALUE: dict[str, float] = {
    "collect_sources": 0.40,
    "extract_claims": 0.30,
    "search_evidence": 0.35,
    "summarize": 0.10,
    "detect_conflicts": 0.25,
    "generate_hypotheses": 0.35,
    "design_experiment": 0.30,
    "run_experiment": 0.50,
    "evaluate_results": 0.20,
}


class PlanSimulator:
    """Lightweight plan simulator.

    Scores each step in a candidate plan using configurable value
    estimates and optional graph-awareness.

    Usage::

        sim = PlanSimulator()
        plan = Plan(steps=[Step(operator="collect_sources")])
        scored = sim.simulate(plan)
        assert scored.score is not None
    """

    def __init__(
        self,
        value_table: dict[str, float] | None = None,
        graph_topics: set[str] | None = None,
    ) -> None:
        self._values = value_table or dict(_DEFAULT_VALUE)
        self._graph_topics: set[str] = graph_topics or set()

    def simulate(self, plan: Plan) -> Plan:
        """Score *plan* by summing predicted step values.

        If *graph_topics* indicates a topic is already well-covered, the
        value of ``collect_sources`` steps for that topic is halved.

        Returns the same :class:`Plan` object with its ``score`` attribute
        populated.
        """
        total = 0.0
        for step in plan.steps:
            value = self._values.get(step.operator, 0.1)
            # Graph-aware penalty: reduce value if topic already covered
            topic = step.inputs.get("topic", "")
            if step.operator == "collect_sources" and topic in self._graph_topics:
                value *= 0.5
            total += value
        plan.score = total
        return plan


class PlanGenerator:
    """Generates multiple candidate :class:`Plan` objects for a task."""

    def generate(
        self,
        task_description: str,
        operators: list[str] | None = None,
        max_plans: int = 3,
    ) -> list[Plan]:
        """Return up to *max_plans* candidate plans.

        Each plan combines the provided *operators* in a different order
        or subset to offer the simulator alternative strategies.
        """
        ops = operators or ["collect_sources", "extract_claims", "summarize"]
        plans: list[Plan] = []

        # Full sequence
        plans.append(Plan(
            steps=[Step(operator=op) for op in ops],
            rationale=f"[Task: {task_description}] Full operator sequence",
        ))

        # Reverse sequence (alternative exploration order)
        if len(ops) > 1 and max_plans > 1:
            plans.append(Plan(
                steps=[Step(operator=op) for op in reversed(ops)],
                rationale=f"[Task: {task_description}] Reverse operator sequence",
            ))

        # Each operator solo
        for op in ops:
            if len(plans) >= max_plans:
                break
            plans.append(Plan(
                steps=[Step(operator=op)],
                rationale=f"[Task: {task_description}] Single operator: {op}",
            ))

        return plans[:max_plans]


class PlanSelector:
    """Selects the highest-scoring plan from a set of candidates."""

    def select(self, plans: list[Plan]) -> Plan | None:
        """Return the plan with the highest score, or ``None`` if empty."""
        scored = [p for p in plans if p.score is not None]
        if not scored:
            return None
        return max(scored, key=lambda p: p.score)  # type: ignore[arg-type]
