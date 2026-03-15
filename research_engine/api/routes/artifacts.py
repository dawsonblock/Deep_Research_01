"""Artifact API routes — delegates to canonical artifact store."""
from __future__ import annotations

from typing import Any

from research_engine.core.artifacts.artifact_store import ArtifactStore
from research_engine.core.artifacts.artifact_schema import Artifact


_artifact_store = ArtifactStore()


def create_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new artifact."""
    artifact = Artifact(
        artifact_type=payload.get("type", "unknown"),
        data=payload.get("data", {}),
        confidence=payload.get("confidence", 0.0),
    )
    _artifact_store.store(artifact)
    return artifact.to_dict()


def get_artifact(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Get an artifact by ID."""
    artifact = _artifact_store.get(payload.get("artifact_id", ""))
    if artifact is None:
        return None
    return artifact.to_dict()


def list_artifacts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """List all artifacts, optionally filtered by type."""
    artifact_type = payload.get("type")
    if artifact_type:
        return [a.to_dict() for a in _artifact_store.get_by_type(artifact_type)]
    return [a.to_dict() for a in _artifact_store.all_artifacts()]
