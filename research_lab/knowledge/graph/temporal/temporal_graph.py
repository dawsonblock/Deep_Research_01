"""Temporal graph — adds temporal edges and version nodes to the belief graph."""
from __future__ import annotations

from typing import Any

from research_lab.knowledge.graph.graph_store import GraphStore, GraphNode
from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType
from research_lab.knowledge.graph.temporal.version_tracker import VersionTracker, Revision


class TemporalGraph:
    """Extends the graph store with temporal version nodes and edges."""

    def __init__(self, store: GraphStore, tracker: VersionTracker) -> None:
        self.store = store
        self.tracker = tracker

    def add_version_node(self, revision: Revision) -> GraphNode:
        """Create a graph node representing a revision."""
        type_map = {
            "claim": NodeType.BELIEF_STATE,
            "finding": NodeType.FINDING_VERSION,
            "theory": NodeType.THEORY_VERSION,
            "evidence": NodeType.EVIDENCE_SNAPSHOT,
            "experiment": NodeType.EXPERIMENT_REVISION,
        }
        node_type = type_map.get(revision.entity_type, NodeType.BELIEF_STATE)
        return self.store.add_node(
            node_type,
            content=revision.state,
            node_id=revision.revision_id,
            metadata={
                "entity_id": revision.entity_id,
                "version": revision.version,
                "cause": revision.cause,
                "previous_revision_id": revision.previous_revision_id,
            },
        )

    def link_supersedes(self, new_revision_id: str, old_revision_id: str) -> str:
        """Link a new revision to the one it supersedes."""
        edge = self.store.add_edge(
            EdgeType.SUPERSEDES,
            source_id=new_revision_id,
            target_id=old_revision_id,
        )
        return edge.edge_id

    def link_revises(self, revision_id: str, entity_id: str) -> str:
        """Link a revision to the entity it revises."""
        edge = self.store.add_edge(
            EdgeType.REVISES,
            source_id=revision_id,
            target_id=entity_id,
        )
        return edge.edge_id

    def link_causal(
        self,
        edge_type: EdgeType,
        source_id: str,
        target_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a causal temporal edge (strengthened_by, weakened_by, invalidated_by)."""
        if edge_type not in (
            EdgeType.STRENGTHENED_BY,
            EdgeType.WEAKENED_BY,
            EdgeType.INVALIDATED_BY,
        ):
            raise ValueError(f"Expected causal edge type, got {edge_type}")
        edge = self.store.add_edge(
            edge_type,
            source_id=source_id,
            target_id=target_id,
            metadata=metadata,
        )
        return edge.edge_id

    def link_observed_at(self, entity_id: str, revision_id: str) -> str:
        """Link an entity to a revision where it was observed."""
        edge = self.store.add_edge(
            EdgeType.OBSERVED_AT,
            source_id=entity_id,
            target_id=revision_id,
        )
        return edge.edge_id

    def get_version_chain(self, entity_type: str, entity_id: str) -> list[GraphNode]:
        """Get all version nodes for an entity in chronological order."""
        revisions = self.tracker.revision_history(entity_type, entity_id)
        nodes: list[GraphNode] = []
        for rev in revisions:
            try:
                node = self.store.get_node(rev.revision_id)
                nodes.append(node)
            except KeyError:
                continue
        return nodes
