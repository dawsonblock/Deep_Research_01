"""In-memory artifact storage and retrieval."""
from __future__ import annotations

from research_engine.core.artifacts.artifact_schema import Artifact


class ArtifactStore:
    """Stores and retrieves artifacts by ID."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def store(self, artifact: Artifact) -> Artifact:
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def get_by_type(self, artifact_type: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def get_by_run(self, producer_run: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.producer_run == producer_run]

    def remove(self, artifact_id: str) -> None:
        self._artifacts.pop(artifact_id, None)

    def all_artifacts(self) -> list[Artifact]:
        return list(self._artifacts.values())

    def count(self) -> int:
        return len(self._artifacts)
