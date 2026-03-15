"""Tests for the belief system modules."""
from __future__ import annotations

import pytest


class TestBeliefModel:
    def test_create_belief(self):
        from research_engine.beliefs.belief_model import Belief
        b = Belief(claim_id="c1", confidence=0.7)
        assert b.belief_id
        assert b.claim_id == "c1"
        assert b.confidence == 0.7

    def test_to_dict(self):
        from research_engine.beliefs.belief_model import Belief
        b = Belief(belief_id="b1", claim_id="c1")
        d = b.to_dict()
        assert d["belief_id"] == "b1"


class TestBeliefStore:
    def test_store_and_get(self):
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        b = Belief(claim_id="c1", confidence=0.6)
        store.store(b)
        assert store.get(b.belief_id) is not None

    def test_get_by_claim(self):
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        b = Belief(claim_id="c1")
        store.store(b)
        found = store.get_by_claim("c1")
        assert found is not None
        assert found.claim_id == "c1"

    def test_update_confidence(self):
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        b = Belief(claim_id="c1", confidence=0.5)
        store.store(b)
        store.update_confidence("c1", 0.9)
        assert store.get_by_claim("c1").confidence == 0.9

    def test_count(self):
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        store.store(Belief(claim_id="c1"))
        store.store(Belief(claim_id="c2"))
        assert store.count() == 2


class TestBeliefUpdater:
    def test_update_creates_belief(self):
        from research_engine.beliefs.belief_updater import BeliefUpdater
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.graph.graph_store import GraphStore
        store = BeliefStore()
        graph = GraphStore()
        updater = BeliefUpdater(store, graph)
        result = updater.update("c1")
        assert "new_confidence" in result
        assert store.count() == 1

    def test_update_with_evidence(self):
        from research_engine.beliefs.belief_updater import BeliefUpdater
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        store = BeliefStore()
        graph = GraphStore()
        claim = graph.add_node(NodeType.CLAIM, {"text": "test"}, node_id="c1")
        ev = graph.add_node(NodeType.EVIDENCE, {"text": "proof"}, metadata={"confidence": 0.9})
        graph.add_edge(EdgeType.SUPPORTS, ev.node_id, "c1")
        updater = BeliefUpdater(store, graph)
        result = updater.update("c1")
        assert result["new_confidence"] > 0


class TestBeliefQuery:
    def test_low_confidence(self):
        from research_engine.beliefs.belief_query import BeliefQuery
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        store.store(Belief(claim_id="c1", confidence=0.2))
        store.store(Belief(claim_id="c2", confidence=0.8))
        query = BeliefQuery(store)
        low = query.low_confidence(0.5)
        assert len(low) == 1
        assert low[0].claim_id == "c1"

    def test_high_confidence(self):
        from research_engine.beliefs.belief_query import BeliefQuery
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        store.store(Belief(claim_id="c1", confidence=0.2))
        store.store(Belief(claim_id="c2", confidence=0.8))
        query = BeliefQuery(store)
        high = query.high_confidence(0.8)
        assert len(high) == 1

    def test_most_uncertain(self):
        from research_engine.beliefs.belief_query import BeliefQuery
        from research_engine.beliefs.belief_store import BeliefStore
        from research_engine.beliefs.belief_model import Belief
        store = BeliefStore()
        store.store(Belief(claim_id="c1", confidence=0.5))
        store.store(Belief(claim_id="c2", confidence=0.1))
        query = BeliefQuery(store)
        uncertain = query.most_uncertain(1)
        assert len(uncertain) == 1
        assert uncertain[0].claim_id == "c1"
