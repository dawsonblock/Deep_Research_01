"""Graph store — typed node/edge storage for the belief graph."""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any

from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType


@dataclass
class GraphNode:
    node_id: str
    node_type: NodeType
    content: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class GraphEdge:
    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class GraphStore:
    """In-memory typed graph store for the belief graph.

    Stores nodes (claim, evidence, hypothesis, ...) and edges
    (supports, contradicts, tests, ...) with full provenance.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        # adjacency indexes: node_id → set of edge_ids
        self._outgoing: dict[str, set[str]] = {}
        self._incoming: dict[str, set[str]] = {}

    # ── node operations ──────────────────────────────────────────────

    def add_node(
        self,
        node_type: NodeType,
        content: dict[str, Any],
        *,
        node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        nid = node_id or uuid.uuid4().hex
        now = time.time()
        node = GraphNode(
            node_id=nid,
            node_type=node_type,
            content=content,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._nodes[nid] = node
        self._outgoing.setdefault(nid, set())
        self._incoming.setdefault(nid, set())
        return node

    def get_node(self, node_id: str) -> GraphNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"Node not found: {node_id}")
        return node

    def update_node(
        self,
        node_id: str,
        content: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        node = self.get_node(node_id)
        if content is not None:
            node.content = content
        if metadata is not None:
            node.metadata = {**node.metadata, **metadata}
        node.updated_at = time.time()
        return node

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"Node not found: {node_id}")
        # remove all connected edges
        edge_ids = set()
        edge_ids.update(self._outgoing.get(node_id, set()))
        edge_ids.update(self._incoming.get(node_id, set()))
        for eid in edge_ids:
            self._remove_edge_internal(eid)
        del self._nodes[node_id]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)

    def query_nodes(
        self,
        *,
        node_type: NodeType | None = None,
        content_filter: dict[str, Any] | None = None,
    ) -> list[GraphNode]:
        results = list(self._nodes.values())
        if node_type is not None:
            results = [n for n in results if n.node_type == node_type]
        if content_filter:
            filtered = []
            for n in results:
                match = all(n.content.get(k) == v for k, v in content_filter.items())
                if match:
                    filtered.append(n)
            results = filtered
        return sorted(results, key=lambda n: n.created_at)

    # ── edge operations ──────────────────────────────────────────────

    def add_edge(
        self,
        edge_type: EdgeType,
        source_id: str,
        target_id: str,
        *,
        edge_id: str | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        # validate endpoints exist
        if source_id not in self._nodes:
            raise KeyError(f"Source node not found: {source_id}")
        if target_id not in self._nodes:
            raise KeyError(f"Target node not found: {target_id}")

        eid = edge_id or uuid.uuid4().hex
        edge = GraphEdge(
            edge_id=eid,
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            weight=weight,
            metadata=metadata or {},
            created_at=time.time(),
        )
        self._edges[eid] = edge
        self._outgoing.setdefault(source_id, set()).add(eid)
        self._incoming.setdefault(target_id, set()).add(eid)
        return edge

    def get_edge(self, edge_id: str) -> GraphEdge:
        edge = self._edges.get(edge_id)
        if edge is None:
            raise KeyError(f"Edge not found: {edge_id}")
        return edge

    def _remove_edge_internal(self, edge_id: str) -> None:
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return
        self._outgoing.get(edge.source_id, set()).discard(edge_id)
        self._incoming.get(edge.target_id, set()).discard(edge_id)

    def remove_edge(self, edge_id: str) -> None:
        if edge_id not in self._edges:
            raise KeyError(f"Edge not found: {edge_id}")
        self._remove_edge_internal(edge_id)

    def query_edges(
        self,
        *,
        edge_type: EdgeType | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]:
        results = list(self._edges.values())
        if edge_type is not None:
            results = [e for e in results if e.edge_type == edge_type]
        if source_id is not None:
            results = [e for e in results if e.source_id == source_id]
        if target_id is not None:
            results = [e for e in results if e.target_id == target_id]
        return sorted(results, key=lambda e: e.created_at)

    # ── traversal helpers ────────────────────────────────────────────

    def neighbors(
        self, node_id: str, *, direction: str = "outgoing"
    ) -> list[GraphNode]:
        if direction == "outgoing":
            edge_ids = self._outgoing.get(node_id, set())
            target_ids = [self._edges[eid].target_id for eid in edge_ids if eid in self._edges]
        elif direction == "incoming":
            edge_ids = self._incoming.get(node_id, set())
            target_ids = [self._edges[eid].source_id for eid in edge_ids if eid in self._edges]
        elif direction == "both":
            out_ids = self._outgoing.get(node_id, set())
            in_ids = self._incoming.get(node_id, set())
            target_ids = [self._edges[eid].target_id for eid in out_ids if eid in self._edges]
            target_ids += [self._edges[eid].source_id for eid in in_ids if eid in self._edges]
        else:
            raise ValueError(f"Invalid direction: {direction}")

        return [self._nodes[nid] for nid in target_ids if nid in self._nodes]

    def subgraph(self, node_ids: set[str]) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Return nodes and edges where both endpoints are in node_ids."""
        nodes = [self._nodes[nid] for nid in node_ids if nid in self._nodes]
        edges = [
            e for e in self._edges.values()
            if e.source_id in node_ids and e.target_id in node_ids
        ]
        return nodes, edges

    # ── convenience ──────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._outgoing.clear()
        self._incoming.clear()
