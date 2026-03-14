"""Reasoning rules for inference."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ReasoningRule:
    """A rule for logical inference."""
    name: str
    description: str = ""
    premise_types: list[str] = None
    conclusion_type: str = ""

    def __post_init__(self) -> None:
        if self.premise_types is None:
            self.premise_types = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "premise_types": list(self.premise_types),
            "conclusion_type": self.conclusion_type,
        }


class ReasoningRuleRegistry:
    """Registry of reasoning rules."""

    def __init__(self) -> None:
        self._rules: dict[str, ReasoningRule] = {}

    def register(self, rule: ReasoningRule) -> None:
        self._rules[rule.name] = rule

    def get(self, name: str) -> ReasoningRule | None:
        return self._rules.get(name)

    def all_rules(self) -> list[ReasoningRule]:
        return list(self._rules.values())
