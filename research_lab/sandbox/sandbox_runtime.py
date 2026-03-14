"""Sandboxed code execution runtime."""
from __future__ import annotations
from dataclasses import dataclass, field

from research_lab.sandbox.resource_limits import ResourceLimits
from research_lab.sandbox.security_policy import SecurityPolicy


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""
    success: bool = False
    output: str = ""
    error: str = ""
    runtime_ms: float = 0.0
    resources_used: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "runtime_ms": self.runtime_ms,
            "resources_used": self.resources_used,
        }


class SandboxRuntime:
    """Executes code in a restricted sandbox environment."""

    def __init__(
        self,
        limits: ResourceLimits | None = None,
        policy: SecurityPolicy | None = None,
    ) -> None:
        self.limits = limits or ResourceLimits()
        self.policy = policy or SecurityPolicy()

    def execute(self, code: str, context: dict | None = None) -> SandboxResult:
        """Execute code in sandbox. Returns result without actual execution (stub)."""
        if not self.policy.is_allowed(code):
            return SandboxResult(
                success=False,
                error="Code rejected by security policy",
            )

        # Stub: real implementation would use subprocess/container
        return SandboxResult(
            success=True,
            output="[sandbox stub] Code accepted for execution",
            resources_used={"cpu_limit": self.limits.cpu_seconds, "memory_limit_mb": self.limits.memory_mb},
        )
