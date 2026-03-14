"""Action rules for the research planner."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ActionRule:
    """A rule that maps a condition to a recommended action."""
    name: str
    action: str
    priority: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "action": self.action,
            "priority": self.priority,
            "description": self.description,
        }


class ActionRuleRegistry:
    """Registry of action rules for planner decision-making."""

    def __init__(self) -> None:
        self._rules: list[ActionRule] = []

    def add_rule(self, rule: ActionRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def get_rules(self) -> list[ActionRule]:
        return list(self._rules)

    def get_rules_for_action(self, action: str) -> list[ActionRule]:
        return [r for r in self._rules if r.action == action]
