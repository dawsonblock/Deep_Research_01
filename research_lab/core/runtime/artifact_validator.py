"""Artifact validator — validates output artifacts against type-specific rules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ValidationResult:
    valid: bool
    artifact_id: str
    artifact_type: str
    content_hash: str
    size_bytes: int
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "size_bytes": self.size_bytes,
            "checks": self.checks,
            "errors": self.errors,
        }


def _content_hash(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _content_size(data: Any) -> int:
    return len(json.dumps(data, sort_keys=True, default=str).encode())


# ── built-in validators by artifact type ─────────────────────────────


def _validate_claim_candidate_set(data: dict[str, Any]) -> tuple[bool, list[dict], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    candidates = data.get("candidates", [])
    checks.append({"check": "has_candidates", "passed": len(candidates) > 0})
    if not candidates:
        errors.append("claim_candidate_set must contain at least one candidate")
        return False, checks, errors

    for i, c in enumerate(candidates):
        has_text = bool(c.get("text"))
        checks.append({"check": f"candidate_{i}_has_text", "passed": has_text})
        if not has_text:
            errors.append(f"Candidate {i} missing text")

        has_source = bool(c.get("source_passage_id") or c.get("source_offset"))
        checks.append({"check": f"candidate_{i}_has_source", "passed": has_source})
        if not has_source:
            errors.append(f"Candidate {i} missing source reference")

    valid = len(errors) == 0
    return valid, checks, errors


def _validate_normalized_claim_set(data: dict[str, Any]) -> tuple[bool, list[dict], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    claims = data.get("claims", [])
    checks.append({"check": "has_claims", "passed": len(claims) > 0})
    if not claims:
        errors.append("normalized_claim_set must contain at least one claim")
        return False, checks, errors

    for i, c in enumerate(claims):
        has_text = bool(c.get("text"))
        checks.append({"check": f"claim_{i}_has_text", "passed": has_text})
        if not has_text:
            errors.append(f"Claim {i} missing text")

        has_conf = isinstance(c.get("confidence"), (int, float))
        checks.append({"check": f"claim_{i}_has_confidence", "passed": has_conf})
        if not has_conf:
            errors.append(f"Claim {i} missing confidence score")

        has_provenance = bool(c.get("provenance"))
        checks.append({"check": f"claim_{i}_has_provenance", "passed": has_provenance})
        if not has_provenance:
            errors.append(f"Claim {i} missing provenance")

    valid = len(errors) == 0
    return valid, checks, errors


def _validate_evidence_link_set(data: dict[str, Any]) -> tuple[bool, list[dict], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    links = data.get("links", [])
    checks.append({"check": "has_links", "passed": len(links) > 0})
    if not links:
        errors.append("evidence_link_set must contain at least one link")
        return False, checks, errors

    for i, link in enumerate(links):
        has_claim = bool(link.get("claim_id"))
        has_evidence = bool(link.get("evidence_id"))
        has_strength = isinstance(link.get("strength"), (int, float))
        checks.append({"check": f"link_{i}_valid", "passed": has_claim and has_evidence and has_strength})
        if not (has_claim and has_evidence and has_strength):
            errors.append(f"Link {i} missing required fields (claim_id, evidence_id, strength)")

    valid = len(errors) == 0
    return valid, checks, errors


def _validate_experiment_result(data: dict[str, Any]) -> tuple[bool, list[dict], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    has_metrics = isinstance(data.get("metrics"), dict) and len(data["metrics"]) > 0
    checks.append({"check": "has_metrics", "passed": has_metrics})
    if not has_metrics:
        errors.append("experiment_result must contain non-empty metrics")

    has_hypothesis = bool(data.get("hypothesis_id") or data.get("hypothesis_text"))
    checks.append({"check": "has_hypothesis_ref", "passed": has_hypothesis})
    if not has_hypothesis:
        errors.append("experiment_result must reference a hypothesis")

    valid = len(errors) == 0
    return valid, checks, errors


# ── registry of validators ───────────────────────────────────────────

_VALIDATORS: dict[str, Callable] = {
    "claim_candidate_set": _validate_claim_candidate_set,
    "normalized_claim_set": _validate_normalized_claim_set,
    "evidence_link_set": _validate_evidence_link_set,
    "experiment_result": _validate_experiment_result,
}


class ArtifactValidator:
    """Validates artifacts against type-specific rules and schemas."""

    def __init__(self) -> None:
        self._validators: dict[str, Callable] = dict(_VALIDATORS)

    def register(self, artifact_type: str, validator: Callable) -> None:
        self._validators[artifact_type] = validator

    def validate(self, artifact_id: str, artifact_type: str, data: Any) -> ValidationResult:
        content_hash = _content_hash(data)
        size_bytes = _content_size(data)

        validator = self._validators.get(artifact_type)
        if validator is None:
            # Unknown types pass with a warning
            return ValidationResult(
                valid=True,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                content_hash=content_hash,
                size_bytes=size_bytes,
                checks=[{"check": "type_known", "passed": False}],
                errors=[],
            )

        valid, checks, errors = validator(data)
        return ValidationResult(
            valid=valid,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            size_bytes=size_bytes,
            checks=checks,
            errors=errors,
        )

    @property
    def supported_types(self) -> list[str]:
        return sorted(self._validators.keys())
