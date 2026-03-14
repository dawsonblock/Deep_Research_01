"""Run registry — tracks every operator execution with full provenance."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED_SUCCESS = "verified_success"
    VERIFIED_FAILURE = "verified_failure"
    ARTIFACT_INVALID = "artifact_invalid"
    RUNTIME_ERROR = "runtime_error"


@dataclass
class EnvironmentSnapshot:
    python_version: str = ""
    platform: str = ""
    hostname: str = ""
    pid: int = 0
    env_vars: dict[str, str] = field(default_factory=dict)

    @classmethod
    def capture(cls, env_prefix: str = "RESEARCH_") -> EnvironmentSnapshot:
        filtered_env = {
            k: v for k, v in os.environ.items() if k.startswith(env_prefix)
        }
        return cls(
            python_version=sys.version,
            platform=platform.platform(),
            hostname=platform.node(),
            pid=os.getpid(),
            env_vars=filtered_env,
        )


@dataclass
class ArtifactManifestEntry:
    artifact_id: str
    artifact_type: str
    content_hash: str
    size_bytes: int = 0


@dataclass
class RunRecord:
    run_id: str
    operator_name: str
    operator_family: str = ""
    operator_version: str = ""
    status: RunStatus = RunStatus.PENDING
    input_hash: str = ""
    code_version: str = ""
    environment: EnvironmentSnapshot = field(default_factory=EnvironmentSnapshot)
    artifact_manifest: list[ArtifactManifestEntry] = field(default_factory=list)
    postcondition_report: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_valid: bool | None = None
    postcondition_passed: bool | None = None
    downstream_outcome: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_inputs(inputs: Any) -> str:
    """Compute a deterministic SHA-256 hash of the inputs."""
    raw = json.dumps(inputs, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _detect_code_version() -> str:
    """Best-effort detection of the current code version."""
    # Try git commit hash first
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown"


class RunRegistry:
    """In-memory registry of all run records."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def create_run(
        self,
        operator_name: str,
        inputs: Any,
        *,
        code_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        operator_family: str = "",
        operator_version: str = "",
    ) -> RunRecord:
        run_id = uuid.uuid4().hex
        record = RunRecord(
            run_id=run_id,
            operator_name=operator_name,
            operator_family=operator_family,
            operator_version=operator_version,
            status=RunStatus.PENDING,
            input_hash=_hash_inputs(inputs),
            code_version=code_version or _detect_code_version(),
            environment=EnvironmentSnapshot.capture(),
            created_at=time.time(),
            metadata=metadata or {},
        )
        self._runs[run_id] = record
        return record

    def mark_running(self, run_id: str) -> RunRecord:
        record = self.get(run_id)
        record.status = RunStatus.RUNNING
        record.started_at = time.time()
        return record

    def mark_success(
        self,
        run_id: str,
        artifact_manifest: list[ArtifactManifestEntry] | None = None,
        postcondition_report: dict[str, Any] | None = None,
    ) -> RunRecord:
        record = self.get(run_id)
        record.status = RunStatus.VERIFIED_SUCCESS
        record.finished_at = time.time()
        if record.started_at is not None:
            record.duration_seconds = record.finished_at - record.started_at
        record.artifact_manifest = artifact_manifest or []
        record.postcondition_report = postcondition_report or {}
        record.artifact_valid = True
        record.postcondition_passed = True
        return record

    def mark_failure(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error_message: str | None = None,
        postcondition_report: dict[str, Any] | None = None,
    ) -> RunRecord:
        if status not in (
            RunStatus.VERIFIED_FAILURE,
            RunStatus.ARTIFACT_INVALID,
            RunStatus.RUNTIME_ERROR,
        ):
            raise ValueError(f"Invalid failure status: {status}")
        record = self.get(run_id)
        record.status = status
        record.finished_at = time.time()
        if record.started_at is not None:
            record.duration_seconds = record.finished_at - record.started_at
        record.error_message = error_message
        record.postcondition_report = postcondition_report or {}
        if status == RunStatus.ARTIFACT_INVALID:
            record.artifact_valid = False
        elif status == RunStatus.VERIFIED_FAILURE:
            record.postcondition_passed = False
        return record

    def get(self, run_id: str) -> RunRecord:
        record = self._runs.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        return record

    def list_runs(
        self,
        *,
        operator_name: str | None = None,
        status: RunStatus | None = None,
    ) -> list[RunRecord]:
        results = list(self._runs.values())
        if operator_name is not None:
            results = [r for r in results if r.operator_name == operator_name]
        if status is not None:
            results = [r for r in results if r.status == status]
        return sorted(results, key=lambda r: r.created_at, reverse=True)
