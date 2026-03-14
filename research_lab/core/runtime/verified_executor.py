"""Verified executor — orchestrates operator execution with full verification."""

from __future__ import annotations

import traceback
from typing import Any, Callable, Protocol

from research_lab.core.runtime.run_registry import (
    ArtifactManifestEntry,
    RunRecord,
    RunRegistry,
    RunStatus,
)
from research_lab.core.runtime.artifact_validator import (
    ArtifactValidator,
    ValidationResult,
)
from research_lab.core.runtime.postcondition_verifier import (
    PostconditionReport,
    PostconditionVerifier,
)


class Operator(Protocol):
    """Protocol for an operator that can be executed by the verified executor."""

    @property
    def name(self) -> str: ...

    def __call__(self, inputs: dict[str, Any]) -> dict[str, Any]: ...


class VerifiedExecutor:
    """Runs an operator inside the trust boundary.

    Pipeline:
        1. Create a run record (pending)
        2. Mark running
        3. Execute the operator
        4. Validate each output artifact
        5. Verify postconditions
        6. Mark final status (verified_success | verified_failure | artifact_invalid | runtime_error)
    """

    def __init__(
        self,
        registry: RunRegistry | None = None,
        validator: ArtifactValidator | None = None,
        verifier: PostconditionVerifier | None = None,
    ) -> None:
        self.registry = registry or RunRegistry()
        self.validator = validator or ArtifactValidator()
        self.verifier = verifier or PostconditionVerifier()

    def execute(
        self,
        operator: Operator | Callable[..., dict[str, Any]],
        inputs: dict[str, Any],
        *,
        operator_name: str | None = None,
        code_version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        name = operator_name or getattr(operator, "name", operator.__class__.__name__)

        # 1. Create run record
        record = self.registry.create_run(
            operator_name=name,
            inputs=inputs,
            code_version=code_version,
            metadata=metadata,
        )

        # 2. Mark running
        self.registry.mark_running(record.run_id)

        # 3. Execute operator
        try:
            outputs = operator(inputs)
        except Exception as exc:
            self.registry.mark_failure(
                record.run_id,
                RunStatus.RUNTIME_ERROR,
                error_message=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
            return self.registry.get(record.run_id)

        # 4. Validate artifacts
        artifacts = outputs.get("artifacts", [])
        manifest: list[ArtifactManifestEntry] = []
        validations: list[ValidationResult] = []
        all_valid = True

        for artifact in artifacts:
            aid = artifact.get("id", "unknown")
            atype = artifact.get("type", "unknown")
            adata = artifact.get("data", {})

            result = self.validator.validate(aid, atype, adata)
            validations.append(result)

            manifest.append(
                ArtifactManifestEntry(
                    artifact_id=aid,
                    artifact_type=atype,
                    content_hash=result.content_hash,
                    size_bytes=result.size_bytes,
                )
            )

            if not result.valid:
                all_valid = False

        if not all_valid:
            error_details = []
            for v in validations:
                if not v.valid:
                    error_details.extend(v.errors)
            self.registry.mark_failure(
                record.run_id,
                RunStatus.ARTIFACT_INVALID,
                error_message="; ".join(error_details),
            )
            return self.registry.get(record.run_id)

        # 5. Verify postconditions
        pc_report: PostconditionReport = self.verifier.verify(name, inputs, outputs)

        if not pc_report.all_passed:
            failed_checks = [c.name for c in pc_report.checks if not c.passed]
            self.registry.mark_failure(
                record.run_id,
                RunStatus.VERIFIED_FAILURE,
                error_message=f"Postcondition(s) failed: {failed_checks}",
                postcondition_report=pc_report.to_dict(),
            )
            return self.registry.get(record.run_id)

        # 6. Mark verified success
        self.registry.mark_success(
            record.run_id,
            artifact_manifest=manifest,
            postcondition_report=pc_report.to_dict(),
        )
        return self.registry.get(record.run_id)
