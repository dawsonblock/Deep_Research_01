"""Version tracker for temporal knowledge base entities."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Revision:
    """A single revision of an entity."""
    revision_id: str
    entity_type: str          # e.g. "claim", "finding", "theory", "experiment"
    entity_id: str
    version: int
    previous_revision_id: str | None
    state: dict[str, Any]
    cause: str                 # what triggered this revision
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "version": self.version,
            "previous_revision_id": self.previous_revision_id,
            "state": self.state,
            "cause": self.cause,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class VersionTracker:
    """Tracks revisions for knowledge graph entities."""

    def __init__(self) -> None:
        # entity_key → list of revisions ordered by version
        self._revisions: dict[str, list[Revision]] = {}
        # revision_id → Revision for quick lookup
        self._by_id: dict[str, Revision] = {}

    @staticmethod
    def _key(entity_type: str, entity_id: str) -> str:
        return f"{entity_type}:{entity_id}"

    def create_revision(
        self,
        entity_type: str,
        entity_id: str,
        new_state: dict[str, Any],
        cause: str,
        *,
        previous_version: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Revision:
        """Create a new revision for an entity.

        If previous_version is None, auto-detects previous version from history.
        """
        key = self._key(entity_type, entity_id)
        history = self._revisions.get(key, [])

        if previous_version is not None:
            # Find the specified previous version
            prev_rev = None
            for r in history:
                if r.version == previous_version:
                    prev_rev = r
                    break
            version = previous_version + 1
            prev_id = prev_rev.revision_id if prev_rev else None
        elif history:
            prev_rev = history[-1]
            version = prev_rev.version + 1
            prev_id = prev_rev.revision_id
        else:
            version = 1
            prev_id = None

        revision = Revision(
            revision_id=uuid.uuid4().hex,
            entity_type=entity_type,
            entity_id=entity_id,
            version=version,
            previous_revision_id=prev_id,
            state=dict(new_state),
            cause=cause,
            metadata=metadata or {},
            created_at=time.time(),
        )
        self._revisions.setdefault(key, []).append(revision)
        self._by_id[revision.revision_id] = revision
        return revision

    def latest_version(self, entity_type: str, entity_id: str) -> Revision | None:
        """Get the latest revision for an entity, or None if no history."""
        key = self._key(entity_type, entity_id)
        history = self._revisions.get(key, [])
        return history[-1] if history else None

    def revision_history(self, entity_type: str, entity_id: str) -> list[Revision]:
        """Return the full ordered revision history for an entity."""
        key = self._key(entity_type, entity_id)
        return list(self._revisions.get(key, []))

    def get_revision(self, revision_id: str) -> Revision | None:
        """Lookup a single revision by ID."""
        return self._by_id.get(revision_id)
