"""Tests for the run registry."""

from __future__ import annotations

import pytest

from research_engine.core.runtime.run_registry import (
    RunRegistry,
    RunStatus,
    _hash_inputs,
)


class TestRunRegistry:
    @pytest.fixture()
    def registry(self) -> RunRegistry:
        return RunRegistry()

    def test_create_run(self, registry: RunRegistry) -> None:
        record = registry.create_run("test_operator", {"key": "value"})
        assert record.run_id
        assert record.operator_name == "test_operator"
        assert record.status == RunStatus.PENDING
        assert record.input_hash == _hash_inputs({"key": "value"})
        assert record.created_at > 0

    def test_mark_running(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        registry.mark_running(record.run_id)
        updated = registry.get(record.run_id)
        assert updated.status == RunStatus.RUNNING
        assert updated.started_at is not None

    def test_mark_success(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        registry.mark_running(record.run_id)
        registry.mark_success(record.run_id)
        updated = registry.get(record.run_id)
        assert updated.status == RunStatus.VERIFIED_SUCCESS
        assert updated.finished_at is not None
        assert updated.duration_seconds is not None

    def test_mark_failure_verified(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        registry.mark_running(record.run_id)
        registry.mark_failure(
            record.run_id,
            RunStatus.VERIFIED_FAILURE,
            error_message="postcondition failed",
        )
        updated = registry.get(record.run_id)
        assert updated.status == RunStatus.VERIFIED_FAILURE
        assert updated.error_message == "postcondition failed"

    def test_mark_failure_artifact_invalid(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        registry.mark_running(record.run_id)
        registry.mark_failure(record.run_id, RunStatus.ARTIFACT_INVALID)
        updated = registry.get(record.run_id)
        assert updated.status == RunStatus.ARTIFACT_INVALID

    def test_mark_failure_runtime_error(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        registry.mark_running(record.run_id)
        registry.mark_failure(record.run_id, RunStatus.RUNTIME_ERROR)
        updated = registry.get(record.run_id)
        assert updated.status == RunStatus.RUNTIME_ERROR

    def test_mark_failure_invalid_status_raises(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        with pytest.raises(ValueError):
            registry.mark_failure(record.run_id, RunStatus.PENDING)

    def test_get_missing_run_raises(self, registry: RunRegistry) -> None:
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_runs_all(self, registry: RunRegistry) -> None:
        registry.create_run("op_a", {})
        registry.create_run("op_b", {})
        runs = registry.list_runs()
        assert len(runs) == 2

    def test_list_runs_by_operator(self, registry: RunRegistry) -> None:
        registry.create_run("op_a", {})
        registry.create_run("op_b", {})
        registry.create_run("op_a", {"x": 1})
        runs = registry.list_runs(operator_name="op_a")
        assert len(runs) == 2

    def test_list_runs_by_status(self, registry: RunRegistry) -> None:
        r1 = registry.create_run("op", {})
        registry.create_run("op", {})
        registry.mark_running(r1.run_id)
        runs = registry.list_runs(status=RunStatus.RUNNING)
        assert len(runs) == 1

    def test_input_hash_deterministic(self) -> None:
        h1 = _hash_inputs({"a": 1, "b": 2})
        h2 = _hash_inputs({"b": 2, "a": 1})
        assert h1 == h2

    def test_run_record_to_dict(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {"key": "val"})
        d = record.to_dict()
        assert d["operator_name"] == "op"
        assert d["status"] == RunStatus.PENDING

    def test_environment_snapshot_captured(self, registry: RunRegistry) -> None:
        record = registry.create_run("op", {})
        assert record.environment.python_version
        assert record.environment.platform
        assert record.environment.pid > 0
