"""Tests for the verified executor."""

from __future__ import annotations

import pytest
from typing import Any

from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
from research_engine.core.runtime.artifact_validator import ArtifactValidator
from research_engine.core.runtime.postcondition_verifier import (
    PostconditionVerifier,
    output_not_empty,
    output_matches_expected_type,
)
from research_engine.core.runtime.verified_executor import VerifiedExecutor


def _good_operator(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifacts": [{
            "id": "art-1",
            "type": "normalized_claim_set",
            "data": {
                "claims": [{
                    "text": "Test claim",
                    "confidence": 0.9,
                    "provenance": {"source_passage_id": "p1"},
                }],
            },
        }],
    }


def _bad_artifact_operator(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifacts": [{
            "id": "art-bad",
            "type": "normalized_claim_set",
            "data": {"claims": []},  # empty claims → invalid
        }],
    }


def _crashing_operator(inputs: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("something broke")


def _empty_output_operator(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"artifacts": []}


class TestVerifiedExecutor:
    @pytest.fixture()
    def executor(self) -> VerifiedExecutor:
        return VerifiedExecutor()

    def test_successful_run(self, executor: VerifiedExecutor) -> None:
        record = executor.execute(_good_operator, {"doc": "test"}, operator_name="good_op")
        assert record.status == RunStatus.VERIFIED_SUCCESS
        assert len(record.artifact_manifest) == 1
        assert record.artifact_manifest[0].artifact_type == "normalized_claim_set"
        assert record.duration_seconds is not None
        assert record.postcondition_report

    def test_invalid_artifact_run(self, executor: VerifiedExecutor) -> None:
        record = executor.execute(_bad_artifact_operator, {}, operator_name="bad_art_op")
        assert record.status == RunStatus.ARTIFACT_INVALID
        assert record.error_message

    def test_runtime_error_run(self, executor: VerifiedExecutor) -> None:
        record = executor.execute(_crashing_operator, {}, operator_name="crash_op")
        assert record.status == RunStatus.RUNTIME_ERROR
        assert "RuntimeError" in record.error_message

    def test_postcondition_failure(self) -> None:
        verifier = PostconditionVerifier()
        verifier.register("empty_op", "output_not_empty", output_not_empty)
        executor = VerifiedExecutor(verifier=verifier)
        record = executor.execute(_empty_output_operator, {}, operator_name="empty_op")
        assert record.status == RunStatus.VERIFIED_FAILURE
        assert "output_not_empty" in record.error_message

    def test_postcondition_type_check(self) -> None:
        verifier = PostconditionVerifier()
        verifier.register(
            "good_op",
            "has_claim_set",
            output_matches_expected_type("normalized_claim_set"),
        )
        executor = VerifiedExecutor(verifier=verifier)
        record = executor.execute(_good_operator, {"doc": "test"}, operator_name="good_op")
        assert record.status == RunStatus.VERIFIED_SUCCESS

    def test_run_record_stored_in_registry(self) -> None:
        registry = RunRegistry()
        executor = VerifiedExecutor(registry=registry)
        record = executor.execute(_good_operator, {}, operator_name="op")
        stored = registry.get(record.run_id)
        assert stored.status == record.status

    def test_unknown_artifact_type_passes_validation(self) -> None:
        def custom_op(inputs: dict[str, Any]) -> dict[str, Any]:
            return {
                "artifacts": [{
                    "id": "art-custom",
                    "type": "custom_unknown_type",
                    "data": {"anything": "goes"},
                }],
            }

        executor = VerifiedExecutor()
        record = executor.execute(custom_op, {}, operator_name="custom_op")
        assert record.status == RunStatus.VERIFIED_SUCCESS
