"""Reasoning graph tracks inference chains."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_id: str = ""
    rule: str = ""
    premise_ids: list[str] = field(default_factory=list)
    conclusion_id: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.step_id:
            self.step_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "rule": self.rule,
            "premise_ids": list(self.premise_ids),
            "conclusion_id": self.conclusion_id,
            "confidence": self.confidence,
        }


class ReasoningGraph:
    """Tracks chains of reasoning steps."""

    def __init__(self) -> None:
        self._steps: dict[str, ReasoningStep] = {}
        self._chains: dict[str, list[str]] = {}

    def add_step(self, step: ReasoningStep) -> str:
        self._steps[step.step_id] = step
        return step.step_id

    def get_step(self, step_id: str) -> ReasoningStep | None:
        return self._steps.get(step_id)

    def create_chain(self, chain_id: str, step_ids: list[str] | None = None) -> None:
        self._chains[chain_id] = list(step_ids or [])

    def append_to_chain(self, chain_id: str, step_id: str) -> None:
        if chain_id not in self._chains:
            self._chains[chain_id] = []
        self._chains[chain_id].append(step_id)

    def get_chain(self, chain_id: str) -> list[ReasoningStep]:
        step_ids = self._chains.get(chain_id, [])
        return [self._steps[sid] for sid in step_ids if sid in self._steps]

    def all_steps(self) -> list[ReasoningStep]:
        return list(self._steps.values())
