"""State snapshot — point-in-time world state captures."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from research_engine.graph.graph_store import GraphStore


@dataclass
class Snapshot:
    """A point-in-time snapshot of graph state."""
    snapshot_id: str
    timestamp: float
    topic: str | None = None
    node_data: list[dict[str, Any]] = field(default_factory=list)
    edge_data: list[dict[str, Any]] = field(default_factory=list)
    revision_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "topic": self.topic,
            "node_count": len(self.node_data),
            "edge_count": len(self.edge_data),
            "revision_ids": list(self.revision_ids),
            "metadata": self.metadata,
        }


class StateSnapshot:
    """Stores and retrieves point-in-time world state snapshots."""

    def __init__(self) -> None:
        self._snapshots: dict[str, Snapshot] = {}

    def snapshot_graph_state(
        self,
        store: GraphStore,
        *,
        topic: str | None = None,
        revision_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        """Capture a full snapshot of current graph state."""
        nodes = [n.to_dict() for n in store.query_nodes()]
        edges = [e.to_dict() for e in store.query_edges()]
        snap = Snapshot(
            snapshot_id=uuid.uuid4().hex,
            timestamp=time.time(),
            topic=topic,
            node_data=nodes,
            edge_data=edges,
            revision_ids=revision_ids or [],
            metadata=metadata or {},
        )
        self._snapshots[snap.snapshot_id] = snap
        return snap

    def snapshot_belief_state(
        self,
        store: GraphStore,
        *,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        """Capture a snapshot of belief-related nodes only."""
        from research_engine.graph.node_types import NodeType
        all_nodes = store.query_nodes()
        belief_types = {NodeType.CLAIM, NodeType.EVIDENCE, NodeType.HYPOTHESIS, NodeType.THEORY}
        nodes = [n for n in all_nodes if n.node_type in belief_types]
        if claim_ids:
            claim_id_set = set(claim_ids)
            nodes = [n for n in nodes if n.node_id in claim_id_set or n.node_type != NodeType.CLAIM]
        node_dicts = [n.to_dict() for n in nodes]
        node_ids = {n.node_id for n in nodes}
        edges = [e.to_dict() for e in store.query_edges() if e.source_id in node_ids and e.target_id in node_ids]
        snap = Snapshot(
            snapshot_id=uuid.uuid4().hex,
            timestamp=time.time(),
            topic="belief_state",
            node_data=node_dicts,
            edge_data=edges,
            metadata=metadata or {},
        )
        self._snapshots[snap.snapshot_id] = snap
        return snap

    def load_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Load a previously stored snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> list[Snapshot]:
        """Return all snapshots ordered by timestamp."""
        return sorted(self._snapshots.values(), key=lambda s: s.timestamp)
