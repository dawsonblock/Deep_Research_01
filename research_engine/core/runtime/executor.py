"""Canonical executor — the single public runtime entrypoint.

Orchestrates operator execution through the verified pipeline:
    1. Accept or build RuntimeContext
    2. Resolve operator
    3. Invoke VerifiedExecutor
    4. Validate artifacts
    5. Verify postconditions
    6. Return ExecutionResult
"""
from __future__ import annotations

from typing import Any, Callable

from research_engine.core.runtime.runtime_context import RuntimeContext
from research_engine.core.runtime.execution_result import ExecutionResult
from research_engine.core.runtime.verified_executor import VerifiedExecutor
from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
from research_engine.core.runtime.artifact_validator import ArtifactValidator
from research_engine.core.runtime.postcondition_verifier import PostconditionVerifier


class CanonicalExecutor:
    """Top-level runtime entrypoint.

    Usage::

        executor = CanonicalExecutor()
        executor.register_operator("researcher", researcher_fn)
        result = executor.run_node(context)
    """

    def __init__(
        self,
        registry: RunRegistry | None = None,
        validator: ArtifactValidator | None = None,
        verifier: PostconditionVerifier | None = None,
    ) -> None:
        self._registry = registry or RunRegistry()
        self._validator = validator or ArtifactValidator()
        self._verifier = verifier or PostconditionVerifier()
        self._verified_executor = VerifiedExecutor(
            registry=self._registry,
            validator=self._validator,
            verifier=self._verifier,
        )
        self._operators: dict[str, Callable[..., dict[str, Any]]] = {}

    def register_operator(
        self, name: str, operator: Callable[..., dict[str, Any]]
    ) -> None:
        """Register an operator callable by name."""
        self._operators[name] = operator

    def run_node(self, context: RuntimeContext) -> ExecutionResult:
        """Execute a node using the canonical verified pipeline.

        Args:
            context: RuntimeContext describing what to execute.

        Returns:
            ExecutionResult with status, artifacts, and diagnostics.
        """
        operator = self._operators.get(context.operator_name)
        if operator is None:
            return ExecutionResult(
                status="operator_not_found",
                run_id=context.run_id,
                errors=[f"Operator not found: {context.operator_name}"],
            )

        record = self._verified_executor.execute(
            operator,
            context.inputs,
            operator_name=context.operator_name,
            metadata={
                "project_id": context.project_id,
                "active_node": context.active_node,
                **context.metadata,
            },
        )

        # Map RunStatus to simple status string
        status_map = {
            RunStatus.VERIFIED_SUCCESS: "success",
            RunStatus.ARTIFACT_INVALID: "artifact_invalid",
            RunStatus.VERIFIED_FAILURE: "postcondition_failed",
            RunStatus.RUNTIME_ERROR: "runtime_error",
        }
        status = status_map.get(record.status, record.status.value)

        artifacts = [
            {
                "artifact_id": m.artifact_id,
                "artifact_type": m.artifact_type,
                "content_hash": m.content_hash,
                "size_bytes": m.size_bytes,
            }
            for m in record.artifact_manifest
        ]

        errors = []
        if record.error_message:
            errors.append(record.error_message)

        return ExecutionResult(
            status=status,
            run_id=record.run_id,
            artifacts=artifacts,
            postconditions=record.postcondition_report,
            errors=errors,
        )

    @property
    def run_registry(self) -> RunRegistry:
        """Access the underlying run registry."""
        return self._registry
