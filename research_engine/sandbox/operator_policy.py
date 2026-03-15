"""Operator policy — maps operators to sandbox policies.

Each operator is assigned a policy that defines its execution constraints
(timeout, memory, network access, capability class).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.sandbox.operator_context import OperatorContext


# Default policies by capability class
_DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "read_only": {
        "network_enabled": False,
        "timeout": 30,
        "memory_budget_mb": 256,
        "capability_class": "read_only",
    },
    "read_write": {
        "network_enabled": False,
        "timeout": 60,
        "memory_budget_mb": 512,
        "capability_class": "read_write",
    },
    "full": {
        "network_enabled": True,
        "timeout": 120,
        "memory_budget_mb": 1024,
        "capability_class": "full",
    },
}


class OperatorPolicy:
    """Maps operator names to their sandbox execution policies."""

    def __init__(self) -> None:
        self._operator_policies: dict[str, str] = {}
        self._custom_contexts: dict[str, OperatorContext] = {}

    def assign(self, operator_name: str, capability_class: str) -> None:
        """Assign a capability class to an operator."""
        self._operator_policies[operator_name] = capability_class

    def assign_custom(self, operator_name: str, context: OperatorContext) -> None:
        """Assign a fully custom context to an operator."""
        self._custom_contexts[operator_name] = context

    def get_context(self, operator_name: str) -> OperatorContext:
        """Resolve the OperatorContext for a given operator name."""
        if operator_name in self._custom_contexts:
            return self._custom_contexts[operator_name]

        cap_class = self._operator_policies.get(operator_name, "read_only")
        defaults = _DEFAULT_POLICIES.get(cap_class, _DEFAULT_POLICIES["read_only"])
        return OperatorContext(**defaults)
