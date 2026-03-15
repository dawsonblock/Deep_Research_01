"""Artifact API routes — delegates to canonical artifact store."""
from __future__ import annotations

from typing import Any

from research_engine.core.artifacts.artifact_store import ArtifactStore
from research_engine.core.artifacts.artifact_schema import Artifact


_artifact_store: ArtifactStore | None = None


def set_artifact_store(store: ArtifactStore) -> None:
    """Configure the artifact routes to use a shared ArtifactStore instance.

    Call this during application startup so that the API layer and
    execution layer share the same canonical store.
    """
    global _artifact_store
    _artifact_store = store


def get_artifact_store() -> ArtifactStore:
    """Return the ArtifactStore used by artifact routes.

    If no store has been injected yet, a default in-memory ArtifactStore is
    created. This preserves previous behavior while still allowing the
    application to inject a shared instance via ``set_artifact_store()``.
    """
    global _artifact_store
    if _artifact_store is None:
        _artifact_store = ArtifactStore()
    return _artifact_store


def create_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new artifact."""
    artifact = Artifact(
        artifact_type=payload.get("type", "unknown"),
        data=payload.get("data", {}),
        confidence=payload.get("confidence", 0.0),
    )
    get_artifact_store().store(artifact)
    return artifact.to_dict()


def get_artifact(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Get an artifact by ID."""
    artifact = get_artifact_store().get(payload.get("artifact_id", ""))
    if artifact is None:
        return None
    return artifact.to_dict()


def list_artifacts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """List all artifacts, optionally filtered by type."""
    store = get_artifact_store()
    artifact_type = payload.get("type")
    if artifact_type:
        return [a.to_dict() for a in store.get_by_type(artifact_type)]
    return [a.to_dict() for a in store.all_artifacts()]
