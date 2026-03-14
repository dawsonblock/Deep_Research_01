"""Tests for research_engine canonical namespace modules.

Validates that all modules in the research_engine package import cleanly,
function correctly, and match the expected interfaces.
"""
from __future__ import annotations

import pytest


# ── Step 3: Runtime truth layer ──────────────────────────────────────


class TestCanonicalRunRegistry:
    def test_create_and_list(self):
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus

        reg = RunRegistry()
        rec = reg.create_run("op1", {"key": "val"})
        assert rec.status == RunStatus.PENDING
        assert rec.operator_name == "op1"
        assert len(reg.list_runs()) == 1

    def test_run_lifecycle(self):
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus

        reg = RunRegistry()
        rec = reg.create_run("op", {"x": 1})
        reg.mark_running(rec.run_id)
        assert reg.get(rec.run_id).status == RunStatus.RUNNING
        reg.mark_success(rec.run_id)
        assert reg.get(rec.run_id).status == RunStatus.VERIFIED_SUCCESS

    def test_failure_statuses(self):
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus

        reg = RunRegistry()
        for status in [RunStatus.VERIFIED_FAILURE, RunStatus.ARTIFACT_INVALID, RunStatus.RUNTIME_ERROR]:
            rec = reg.create_run("op", {})
            reg.mark_running(rec.run_id)
            reg.mark_failure(rec.run_id, status, error_message="test")
            assert reg.get(rec.run_id).status == status

    def test_filter_by_operator(self):
        from research_engine.core.runtime.run_registry import RunRegistry

        reg = RunRegistry()
        reg.create_run("alpha", {})
        reg.create_run("beta", {})
        reg.create_run("alpha", {})
        assert len(reg.list_runs(operator_name="alpha")) == 2
        assert len(reg.list_runs(operator_name="beta")) == 1


class TestCanonicalArtifactValidator:
    def test_validate_valid_claim_set(self):
        from research_engine.core.runtime.artifact_validator import ArtifactValidator

        validator = ArtifactValidator()
        result = validator.validate("a1", "normalized_claim_set", {
            "claims": [{"text": "A claim", "confidence": 0.9, "provenance": "paper"}]
        })
        assert result.valid is True

    def test_validate_invalid_claim_set(self):
        from research_engine.core.runtime.artifact_validator import ArtifactValidator

        validator = ArtifactValidator()
        result = validator.validate("a1", "normalized_claim_set", {"claims": []})
        assert result.valid is False

    def test_unknown_type_passes(self):
        from research_engine.core.runtime.artifact_validator import ArtifactValidator

        validator = ArtifactValidator()
        result = validator.validate("a1", "custom_type", {"anything": True})
        assert result.valid is True


class TestCanonicalVerifiedExecutor:
    def test_successful_execution(self):
        from research_engine.core.runtime.verified_executor import VerifiedExecutor
        from research_engine.core.runtime.run_registry import RunStatus

        def good_op(inputs):
            return {"artifacts": [{"id": "a1", "type": "normalized_claim_set", "data": {
                "claims": [{"text": "X", "confidence": 0.8, "provenance": "test"}]
            }}]}

        executor = VerifiedExecutor()
        record = executor.execute(good_op, {}, operator_name="good_op")
        assert record.status == RunStatus.VERIFIED_SUCCESS

    def test_runtime_error(self):
        from research_engine.core.runtime.verified_executor import VerifiedExecutor
        from research_engine.core.runtime.run_registry import RunStatus

        def bad_op(inputs):
            raise RuntimeError("boom")

        executor = VerifiedExecutor()
        record = executor.execute(bad_op, {}, operator_name="bad_op")
        assert record.status == RunStatus.RUNTIME_ERROR


# ── Step 4: Canonical graph ──────────────────────────────────────────


class TestCanonicalGraphStore:
    def test_add_and_query_nodes(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType

        store = GraphStore()
        store.add_node(NodeType.CLAIM, {"text": "hello"})
        store.add_node(NodeType.EVIDENCE, {"text": "proof"})
        claims = store.query_nodes(node_type=NodeType.CLAIM)
        assert len(claims) == 1
        assert claims[0].content["text"] == "hello"

    def test_edges(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType

        store = GraphStore()
        c = store.add_node(NodeType.CLAIM, {"text": "claim"})
        e = store.add_node(NodeType.EVIDENCE, {"text": "evidence"})
        store.add_edge(EdgeType.SUPPORTS, source_id=e.node_id, target_id=c.node_id)
        edges = store.query_edges(edge_type=EdgeType.SUPPORTS)
        assert len(edges) == 1

    def test_node_types_complete(self):
        from research_engine.graph.node_types import NodeType

        expected = {"claim", "evidence", "hypothesis", "experiment", "result",
                    "finding", "theory", "research_frontier", "belief_state",
                    "finding_version", "theory_version", "evidence_snapshot",
                    "experiment_revision"}
        actual = {nt.value for nt in NodeType}
        assert expected == actual

    def test_edge_types_complete(self):
        from research_engine.graph.edge_types import EdgeType

        expected = {"supports", "contradicts", "tests", "produced", "summarizes",
                    "contributes_to", "investigates", "explores", "supersedes",
                    "revises", "invalidated_by", "strengthened_by", "weakened_by",
                    "observed_at"}
        actual = {et.value for et in EdgeType}
        assert expected == actual


class TestWorldModelAdapter:
    def test_mirror_claim(self):
        from research_engine.graph.world_model_adapter import WorldModelAdapter
        from research_engine.graph.node_types import NodeType

        adapter = WorldModelAdapter()
        nid = adapter.mirror_claim({"id": "c1", "content": "test claim", "confidence": 0.7, "status": "active"})
        assert nid == "c1"
        node = adapter.store.get_node("c1")
        assert node.node_type == NodeType.CLAIM
        assert node.metadata["confidence"] == 0.7

    def test_mirror_hypothesis(self):
        from research_engine.graph.world_model_adapter import WorldModelAdapter
        from research_engine.graph.node_types import NodeType

        adapter = WorldModelAdapter()
        nid = adapter.mirror_hypothesis({"id": "h1", "statement": "maybe", "prediction": "yes", "confidence": 0.6})
        node = adapter.store.get_node("h1")
        assert node.node_type == NodeType.HYPOTHESIS

    def test_mirror_evidence_with_link(self):
        from research_engine.graph.world_model_adapter import WorldModelAdapter
        from research_engine.graph.edge_types import EdgeType

        adapter = WorldModelAdapter()
        adapter.mirror_claim({"id": "c1", "content": "claim"})
        adapter.mirror_evidence({"id": "e1", "content": "proof"}, claim_id="c1")
        edges = adapter.store.query_edges(edge_type=EdgeType.SUPPORTS)
        assert len(edges) == 1
        assert edges[0].source_id == "e1"
        assert edges[0].target_id == "c1"


# ── Step 6: Artifact service ────────────────────────────────────────


class TestCanonicalArtifacts:
    def test_artifact_creation(self):
        from research_engine.core.artifacts.artifact_schema import Artifact

        a = Artifact(artifact_type="claim_set", data={"claims": []})
        assert a.artifact_id
        assert a.artifact_type == "claim_set"

    def test_store_and_retrieve(self):
        from research_engine.core.artifacts.artifact_schema import Artifact
        from research_engine.core.artifacts.artifact_store import ArtifactStore

        store = ArtifactStore()
        a = Artifact(artifact_type="test", data={"x": 1})
        store.store(a)
        assert store.get(a.artifact_id) is a
        assert store.count() == 1

    def test_indexer(self):
        from research_engine.core.artifacts.artifact_schema import Artifact
        from research_engine.core.artifacts.artifact_indexer import ArtifactIndexer

        indexer = ArtifactIndexer()
        a = Artifact(artifact_type="claim", data={}, producer_run="run1")
        indexer.index(a)
        assert a.artifact_id in indexer.lookup_by_type("claim")
        assert a.artifact_id in indexer.lookup_by_run("run1")

    def test_side_effect_processor(self):
        from research_engine.core.artifacts.artifact_schema import Artifact
        from research_engine.core.artifacts.artifact_sideeffects import SideEffectProcessor

        class Noop:
            def process(self, artifact):
                pass

        proc = SideEffectProcessor()
        proc.register(Noop())
        a = Artifact(artifact_type="test", data={})
        results = proc.process(a)
        assert len(results) == 1
        assert results[0] == "Noop"


# ── Step 8: Temporal modules ────────────────────────────────────────


class TestCanonicalTemporal:
    def test_version_tracker(self):
        from research_engine.graph.temporal.version_tracker import VersionTracker

        tracker = VersionTracker()
        rev1 = tracker.create_revision("claim", "c1", {"confidence": 0.5}, "initial")
        assert rev1.version == 1
        rev2 = tracker.create_revision("claim", "c1", {"confidence": 0.8}, "evidence_update")
        assert rev2.version == 2
        assert rev2.previous_revision_id == rev1.revision_id

    def test_belief_timeline(self):
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.graph.temporal.belief_timeline import BeliefTimeline

        tracker = VersionTracker()
        tracker.create_revision("claim", "c1", {"confidence": 0.5}, "init")
        tracker.create_revision("claim", "c1", {"confidence": 0.3}, "weakened")
        timeline = BeliefTimeline(tracker)
        entries = timeline.timeline_for_claim("c1")
        assert len(entries) == 2
        assert entries[0].confidence == 0.5
        assert entries[1].confidence == 0.3

    def test_temporal_graph_version_nodes(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.graph.temporal.temporal_graph import TemporalGraph
        from research_engine.graph.node_types import NodeType

        store = GraphStore()
        tracker = VersionTracker()
        tg = TemporalGraph(store, tracker)
        rev = tracker.create_revision("claim", "c1", {"confidence": 0.7}, "new_evidence")
        node = tg.add_version_node(rev)
        assert node.node_type == NodeType.BELIEF_STATE

    def test_state_snapshot(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.temporal.state_snapshot import StateSnapshot

        store = GraphStore()
        store.add_node(NodeType.CLAIM, {"text": "test"})
        ss = StateSnapshot()
        snap = ss.snapshot_graph_state(store)
        assert len(snap.node_data) == 1


# ── Step 9-10: Planner and instability ──────────────────────────────


class TestCanonicalPlanner:
    def test_select_action(self):
        from research_engine.planner.research_planner import ResearchPlanner, PlannerState

        planner = ResearchPlanner()
        state = PlannerState(unresolved_conflicts=3)
        assert planner.select_action(state) == "detect_conflicts"

    def test_default_action(self):
        from research_engine.planner.research_planner import ResearchPlanner, PlannerState

        planner = ResearchPlanner()
        state = PlannerState()
        assert planner.select_action(state) == "ingest_literature"

    def test_strategy_memory(self):
        from research_engine.planner.strategy_memory import StrategyMemory

        mem = StrategyMemory()
        mem.record_outcome("search", "low_conf", True)
        mem.record_outcome("search", "low_conf", True)
        mem.record_outcome("ingest", "low_conf", False)
        assert mem.best_action_for_context("low_conf") == "search"

    def test_strategy_optimizer(self):
        from research_engine.planner.strategy_memory import StrategyMemory
        from research_engine.planner.strategy_optimizer import StrategyOptimizer

        mem = StrategyMemory()
        mem.record_outcome("a", "ctx", True)
        mem.record_outcome("b", "ctx", False)
        opt = StrategyOptimizer(mem)
        assert opt.select_action(["a", "b"], "ctx") == "a"


class TestTopicManagement:
    def test_create_topic(self):
        from research_engine.planner.agenda.topic_manager import TopicManager

        mgr = TopicManager()
        t = mgr.create_topic("quantum error correction", priority=0.8, uncertainty=0.9)
        assert t.name == "quantum error correction"
        assert len(mgr.active_topics()) == 1

    def test_topic_prioritizer(self):
        from research_engine.planner.agenda.topic_manager import TopicManager, ResearchTopic
        from research_engine.planner.agenda.topic_priority import TopicPrioritizer

        topics = [
            ResearchTopic(name="low", priority=0.1, uncertainty=0.1),
            ResearchTopic(name="high", priority=0.9, uncertainty=0.9),
        ]
        p = TopicPrioritizer()
        ranked = p.rank(topics)
        assert ranked[0].name == "high"

    def test_topic_memory(self):
        from research_engine.planner.agenda.topic_memory import TopicMemory

        mem = TopicMemory()
        mem.record_event("t1", "created", "new topic")
        mem.record_event("t1", "updated", "priority changed")
        events = mem.get_events("t1")
        assert len(events) == 2


class TestInstabilityScorer:
    def test_empty_graph_score(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        scorer = InstabilityScorer(store)
        report = scorer.score()
        assert report.total_score == 0.0

    def test_unsupported_claims(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        store.add_node(NodeType.CLAIM, {"text": "orphan claim"})
        scorer = InstabilityScorer(store)
        report = scorer.score()
        assert report.unsupported_claims == 1

    def test_contradiction_density(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        c1 = store.add_node(NodeType.CLAIM, {"text": "A"})
        c2 = store.add_node(NodeType.CLAIM, {"text": "not A"})
        store.add_edge(EdgeType.CONTRADICTS, c1.node_id, c2.node_id)
        scorer = InstabilityScorer(store)
        report = scorer.score()
        assert report.contradiction_density == 1.0

    def test_weakening_trends(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.graph.temporal.belief_timeline import BeliefTimeline
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        node = store.add_node(NodeType.CLAIM, {"text": "weakening"})
        tracker = VersionTracker()
        tracker.create_revision("claim", node.node_id, {"confidence": 0.9}, "init")
        tracker.create_revision("claim", node.node_id, {"confidence": 0.4}, "weakened")
        timeline = BeliefTimeline(tracker)
        scorer = InstabilityScorer(store, tracker, timeline)
        report = scorer.score()
        assert report.weakening_trends == 1

    def test_revision_churn(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        tracker = VersionTracker()
        tracker.create_revision("claim", "c1", {"conf": 0.5}, "a")
        tracker.create_revision("claim", "c1", {"conf": 0.6}, "b")
        tracker.create_revision("claim", "c1", {"conf": 0.7}, "c")
        scorer = InstabilityScorer(store, tracker)
        report = scorer.score()
        assert report.revision_churn == 3.0  # 3 revisions / 1 entity

    def test_open_hypotheses(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.planner.instability_scorer import InstabilityScorer

        store = GraphStore()
        store.add_node(NodeType.HYPOTHESIS, {"text": "untested"})
        scorer = InstabilityScorer(store)
        report = scorer.score()
        assert report.open_hypotheses == 1


# ── End-to-end: first concrete milestone (claim → weaken → planner sees) ──


class TestClaimToWeakenToPlanner:
    """Integration test: claim flows through canonical runtime → temporal
    graph → instability scorer → planner sees instability."""

    def test_full_pipeline(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.graph.temporal.temporal_graph import TemporalGraph
        from research_engine.graph.temporal.belief_timeline import BeliefTimeline
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
        from research_engine.core.runtime.artifact_validator import ArtifactValidator
        from research_engine.planner.instability_scorer import InstabilityScorer
        from research_engine.planner.research_planner import ResearchPlanner, PlannerState

        # 1. Set up canonical infrastructure
        store = GraphStore()
        tracker = VersionTracker()
        tg = TemporalGraph(store, tracker)
        timeline = BeliefTimeline(tracker)
        registry = RunRegistry()
        validator = ArtifactValidator()

        # 2. Create a claim in the graph (simulating backend flow)
        claim = store.add_node(NodeType.CLAIM, {"text": "Sleep improves memory consolidation"})

        # 3. Record a canonical run for claim creation
        run = registry.create_run("claim_extractor", {"source": "paper_1"})
        registry.mark_running(run.run_id)
        registry.mark_success(run.run_id)

        # 4. Validate the artifact
        val = validator.validate("art1", "normalized_claim_set", {
            "claims": [{"text": "Sleep improves memory consolidation", "confidence": 0.8, "provenance": "paper_1"}]
        })
        assert val.valid

        # 5. Track initial confidence as a revision
        rev1 = tracker.create_revision("claim", claim.node_id, {"confidence": 0.8}, "initial_extraction")
        tg.add_version_node(rev1)

        # 6. Later experiment weakens the claim
        exp = store.add_node(NodeType.EXPERIMENT, {"description": "test sleep claim"})
        result = store.add_node(NodeType.RESULT, {"verdict": "weak support", "metrics": {"p_value": 0.12}})
        store.add_edge(EdgeType.PRODUCED, exp.node_id, result.node_id)
        store.add_edge(EdgeType.WEAKENED_BY, claim.node_id, result.node_id)

        # 7. Create a temporal revision showing weakening
        rev2 = tracker.create_revision("claim", claim.node_id, {"confidence": 0.3}, "experiment_weakened")
        version_node = tg.add_version_node(rev2)
        tg.link_supersedes(rev2.revision_id, rev1.revision_id)

        # 8. Planner sees instability
        scorer = InstabilityScorer(store, tracker, timeline)
        report = scorer.score()
        assert report.weakening_trends >= 1
        assert report.total_score > 0

        # 9. Planner decides to search for more evidence
        planner_state = PlannerState(
            evidence_gaps=report.unsupported_claims,
            unresolved_conflicts=int(report.contradiction_density > 0),
        )
        planner = ResearchPlanner()
        action = planner.select_action(planner_state)
        # With evidence gaps, it should choose search_evidence
        assert action in ResearchPlanner.ACTIONS
