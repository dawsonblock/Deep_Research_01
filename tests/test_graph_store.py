"""Tests for the belief graph store."""

from __future__ import annotations

import pytest

from research_engine.graph.graph_store import GraphStore
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType


class TestGraphStore:
    @pytest.fixture()
    def store(self) -> GraphStore:
        return GraphStore()

    def test_add_and_get_node(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.CLAIM, {"text": "Test claim"})
        fetched = store.get_node(node.node_id)
        assert fetched.node_type == NodeType.CLAIM
        assert fetched.content["text"] == "Test claim"

    def test_add_node_with_custom_id(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.EVIDENCE, {"text": "ev"}, node_id="ev-1")
        assert node.node_id == "ev-1"

    def test_get_missing_node_raises(self, store: GraphStore) -> None:
        with pytest.raises(KeyError):
            store.get_node("nonexistent")

    def test_update_node(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.CLAIM, {"text": "v1"})
        store.update_node(node.node_id, content={"text": "v2"})
        updated = store.get_node(node.node_id)
        assert updated.content["text"] == "v2"

    def test_update_node_metadata_merges(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.CLAIM, {"text": "c"}, metadata={"a": 1})
        store.update_node(node.node_id, metadata={"b": 2})
        updated = store.get_node(node.node_id)
        assert updated.metadata == {"a": 1, "b": 2}

    def test_remove_node(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.CLAIM, {"text": "c"})
        store.remove_node(node.node_id)
        assert store.node_count == 0

    def test_remove_node_cascades_edges(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        store.remove_node(n1.node_id)
        assert store.edge_count == 0

    def test_query_nodes_by_type(self, store: GraphStore) -> None:
        store.add_node(NodeType.CLAIM, {"text": "c1"})
        store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        store.add_node(NodeType.CLAIM, {"text": "c2"})
        claims = store.query_nodes(node_type=NodeType.CLAIM)
        assert len(claims) == 2

    def test_query_nodes_by_content(self, store: GraphStore) -> None:
        store.add_node(NodeType.CLAIM, {"text": "c1", "status": "active"})
        store.add_node(NodeType.CLAIM, {"text": "c2", "status": "retired"})
        results = store.query_nodes(content_filter={"status": "active"})
        assert len(results) == 1

    def test_add_and_get_edge(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        edge = store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id, weight=0.9)
        fetched = store.get_edge(edge.edge_id)
        assert fetched.edge_type == EdgeType.SUPPORTS
        assert fetched.weight == 0.9

    def test_add_edge_missing_source_raises(self, store: GraphStore) -> None:
        n = store.add_node(NodeType.CLAIM, {"text": "c"})
        with pytest.raises(KeyError):
            store.add_edge(EdgeType.SUPPORTS, "missing", n.node_id)

    def test_add_edge_missing_target_raises(self, store: GraphStore) -> None:
        n = store.add_node(NodeType.CLAIM, {"text": "c"})
        with pytest.raises(KeyError):
            store.add_edge(EdgeType.SUPPORTS, n.node_id, "missing")

    def test_remove_edge(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        edge = store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        store.remove_edge(edge.edge_id)
        assert store.edge_count == 0

    def test_remove_missing_edge_raises(self, store: GraphStore) -> None:
        with pytest.raises(KeyError):
            store.remove_edge("nonexistent")

    def test_query_edges_by_type(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        n3 = store.add_node(NodeType.CLAIM, {"text": "c2"})
        store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        store.add_edge(EdgeType.CONTRADICTS, n1.node_id, n3.node_id)
        supports = store.query_edges(edge_type=EdgeType.SUPPORTS)
        assert len(supports) == 1
        contradicts = store.query_edges(edge_type=EdgeType.CONTRADICTS)
        assert len(contradicts) == 1

    def test_query_edges_by_source(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        edges = store.query_edges(source_id=n2.node_id)
        assert len(edges) == 1

    def test_neighbors_outgoing(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        store.add_edge(EdgeType.SUPPORTS, n1.node_id, n2.node_id)
        neighbors = store.neighbors(n1.node_id, direction="outgoing")
        assert len(neighbors) == 1
        assert neighbors[0].node_id == n2.node_id

    def test_neighbors_incoming(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        store.add_edge(EdgeType.SUPPORTS, n1.node_id, n2.node_id)
        neighbors = store.neighbors(n2.node_id, direction="incoming")
        assert len(neighbors) == 1
        assert neighbors[0].node_id == n1.node_id

    def test_neighbors_both(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        n3 = store.add_node(NodeType.HYPOTHESIS, {"text": "h1"})
        store.add_edge(EdgeType.SUPPORTS, n1.node_id, n2.node_id)
        store.add_edge(EdgeType.TESTS, n3.node_id, n1.node_id)
        neighbors = store.neighbors(n1.node_id, direction="both")
        assert len(neighbors) == 2

    def test_subgraph(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        n3 = store.add_node(NodeType.CLAIM, {"text": "c2"})
        store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        store.add_edge(EdgeType.CONTRADICTS, n1.node_id, n3.node_id)
        nodes, edges = store.subgraph({n1.node_id, n2.node_id})
        assert len(nodes) == 2
        assert len(edges) == 1  # only the supports edge

    def test_clear(self, store: GraphStore) -> None:
        store.add_node(NodeType.CLAIM, {"text": "c1"})
        store.clear()
        assert store.node_count == 0
        assert store.edge_count == 0

    def test_node_to_dict(self, store: GraphStore) -> None:
        node = store.add_node(NodeType.CLAIM, {"text": "c"})
        d = node.to_dict()
        assert d["node_type"] == "claim"
        assert d["content"]["text"] == "c"

    def test_edge_to_dict(self, store: GraphStore) -> None:
        n1 = store.add_node(NodeType.CLAIM, {"text": "c1"})
        n2 = store.add_node(NodeType.EVIDENCE, {"text": "e1"})
        edge = store.add_edge(EdgeType.SUPPORTS, n2.node_id, n1.node_id)
        d = edge.to_dict()
        assert d["edge_type"] == "supports"

    def test_all_node_types(self, store: GraphStore) -> None:
        for nt in NodeType:
            store.add_node(nt, {"text": f"node of type {nt.value}"})
        assert store.node_count == len(NodeType)

    def test_all_edge_types(self, store: GraphStore) -> None:
        nodes = []
        for i in range(len(EdgeType) + 1):
            nodes.append(store.add_node(NodeType.CLAIM, {"text": f"n{i}"}))
        for i, et in enumerate(EdgeType):
            store.add_edge(et, nodes[i].node_id, nodes[i + 1].node_id)
        assert store.edge_count == len(EdgeType)
