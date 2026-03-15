"""Runtime harness — canonical sandbox execution harness.

This module is the primary entrypoint for sandboxed operator execution.
It wraps the existing SandboxRuntime with policy-aware context resolution.
"""
from __future__ import annotations

from typing import Any

from research_engine.sandbox.sandbox_runtime import SandboxRuntime, SandboxResult
from research_engine.sandbox.operator_context import OperatorContext
from research_engine.sandbox.operator_policy import OperatorPolicy
from research_engine.sandbox.resource_limits import ResourceLimits
from research_engine.sandbox.security_policy import SecurityPolicy


class RuntimeHarness:
    """Policy-aware sandbox execution harness.

    Resolves operator policies, configures sandbox limits, and delegates
    execution to SandboxRuntime.
    """

    def __init__(
        self,
        policy: OperatorPolicy | None = None,
        security: SecurityPolicy | None = None,
    ) -> None:
        self._policy = policy or OperatorPolicy()
        self._security = security or SecurityPolicy()

    def execute(
        self,
        operator_name: str,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> SandboxResult:
        """Execute code in a sandbox configured for the given operator.

        Args:
            operator_name: Name of the operator requesting execution.
            code: Code string to execute.
            context: Optional additional context passed to the sandbox.

        Returns:
            SandboxResult from the execution.
        """
        op_ctx = self._policy.get_context(operator_name)
        limits = ResourceLimits(
            cpu_seconds=op_ctx.timeout,
            memory_mb=op_ctx.memory_budget_mb,
            network_enabled=op_ctx.network_enabled,
        )
        runtime = SandboxRuntime(limits=limits, policy=self._security)
        return runtime.execute(code, context)

    @property
    def operator_policy(self) -> OperatorPolicy:
        return self._policy
