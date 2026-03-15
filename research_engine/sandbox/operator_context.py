"""Operator context — defines the execution environment for an operator.

Attributes:
    allowed_paths: Filesystem paths the operator may access.
    network_enabled: Whether outbound network access is permitted.
    timeout: Maximum execution time in seconds.
    memory_budget_mb: Maximum memory in megabytes.
    capability_class: Operator capability class (e.g. 'read_only', 'read_write', 'full').
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperatorContext:
    """Execution environment constraints for a sandboxed operator."""

    allowed_paths: list[str] = field(default_factory=list)
    network_enabled: bool = False
    timeout: int = 30
    memory_budget_mb: int = 256
    capability_class: str = "read_only"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_paths": self.allowed_paths,
            "network_enabled": self.network_enabled,
            "timeout": self.timeout,
            "memory_budget_mb": self.memory_budget_mb,
            "capability_class": self.capability_class,
            "metadata": self.metadata,
        }
