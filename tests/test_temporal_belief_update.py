"""Tests for temporal belief update integration."""
import pytest
from research_lab.knowledge.graph.graph_store import GraphStore
from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType
from research_lab.knowledge.belief.belief_graph import BeliefGraph
from research_lab.knowledge.belief.belief_update import BeliefUpdater
from research_lab.knowledge.graph.temporal.version_tracker import VersionTracker
from research_lab.knowledge.graph.temporal.temporal_graph import TemporalGraph
from research_lab.knowledge.graph.temporal.belief_timeline import BeliefTimeline


class TestTemporalBeliefUpdate:
    def setup_method(self):
        self.store = GraphStore()
        self.belief_graph = BeliefGraph(self.store)
        self.tracker = VersionTracker()
        self.temporal_graph = TemporalGraph(self.store, self.tracker)
        self.updater = BeliefUpdater(
            self.belief_graph,
            tracker=self.tracker,
            temporal_graph=self.temporal_graph,
        )
        self.timeline = BeliefTimeline(self.tracker)

    def test_update_creates_revision(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        result = self.updater.update_claim_confidence(claim.node_id)
        assert result["revision_id"] is not None
        rev = self.tracker.latest_version("claim", claim.node_id)
        assert rev is not None
        assert rev.version == 1

    def test_update_preserves_old_confidence(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        result = self.updater.update_claim_confidence(claim.node_id)
        rev = self.tracker.latest_version("claim", claim.node_id)
        assert rev.state["old_confidence"] == 0.5

    def test_sequential_updates_build_history(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        self.updater.update_claim_confidence(claim.node_id, cause="first")
        # Add supporting evidence
        ev = self.store.add_node(NodeType.EVIDENCE, {"text": "supports"}, metadata={"confidence": 0.9})
        self.store.add_edge(EdgeType.SUPPORTS, ev.node_id, claim.node_id, metadata={"weight": 1.0})
        self.updater.update_claim_confidence(claim.node_id, cause="second")
        history = self.tracker.revision_history("claim", claim.node_id)
        assert len(history) == 2
        assert history[1].cause == "second"

    def test_timeline_reflects_updates(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        self.updater.update_claim_confidence(claim.node_id, cause="initial")
        ev = self.store.add_node(NodeType.EVIDENCE, {"text": "strong"}, metadata={"confidence": 0.9})
        self.store.add_edge(EdgeType.SUPPORTS, ev.node_id, claim.node_id, metadata={"weight": 1.0})
        self.updater.update_claim_confidence(claim.node_id, cause="new_evidence")
        entries = self.timeline.timeline_for_claim(claim.node_id)
        assert len(entries) == 2

    def test_backward_compatible_without_tracker(self):
        """BeliefUpdater works without temporal tracking (backward compat)."""
        updater = BeliefUpdater(self.belief_graph)
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        result = updater.update_claim_confidence(claim.node_id)
        # Should still return a dict with confidence info
        assert "new_confidence" in result
        assert result["revision_id"] is None

    def test_version_node_created_in_graph(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        result = self.updater.update_claim_confidence(claim.node_id)
        rev_id = result["revision_id"]
        # The revision should exist as a graph node
        node = self.store.get_node(rev_id)
        assert node.node_type == NodeType.BELIEF_STATE

    def test_supersedes_edge_created(self):
        claim = self.store.add_node(NodeType.CLAIM, {"text": "test"}, metadata={"confidence": 0.5})
        self.updater.update_claim_confidence(claim.node_id, cause="first")
        # Add supporting evidence
        ev = self.store.add_node(NodeType.EVIDENCE, {"text": "supports"}, metadata={"confidence": 0.9})
        self.store.add_edge(EdgeType.SUPPORTS, ev.node_id, claim.node_id, metadata={"weight": 1.0})
        self.updater.update_claim_confidence(claim.node_id, cause="second")
        # Check for supersedes edges
        supersedes_edges = self.store.query_edges(edge_type=EdgeType.SUPERSEDES)
        assert len(supersedes_edges) >= 1
