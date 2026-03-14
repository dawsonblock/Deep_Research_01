"""Indexes artifacts for fast lookup by various fields."""
from __future__ import annotations
from collections import defaultdict

from research_lab.core.artifacts.artifact_schema import Artifact


class ArtifactIndexer:
    """Maintains secondary indexes over the artifact store."""

    def __init__(self) -> None:
        self._by_type: dict[str, list[str]] = defaultdict(list)
        self._by_run: dict[str, list[str]] = defaultdict(list)

    def index(self, artifact: Artifact) -> None:
        self._by_type[artifact.artifact_type].append(artifact.artifact_id)
        if artifact.producer_run:
            self._by_run[artifact.producer_run].append(artifact.artifact_id)

    def lookup_by_type(self, artifact_type: str) -> list[str]:
        return list(self._by_type.get(artifact_type, []))

    def lookup_by_run(self, producer_run: str) -> list[str]:
        return list(self._by_run.get(producer_run, []))
