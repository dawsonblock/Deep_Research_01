"""Tests for new research_engine canonical modules (Phases 7–16).

Validates that all migrated modules import cleanly, function correctly,
and match the expected interfaces.  These tests must NOT require a database
or any backend dependency.
"""
from __future__ import annotations

import pytest


# ── Phase 7: Experiment System ───────────────────────────────────────


class TestExperimentSpec:
    def test_create_spec(self):
        from research_engine.experiments.experiment_spec import ExperimentSpec

        spec = ExperimentSpec(hypothesis="H1", variables={"x": 1})
        assert spec.hypothesis == "H1"
        assert spec.spec_id  # auto-generated

    def test_spec_to_dict(self):
        from research_engine.experiments.experiment_spec import ExperimentSpec

        spec = ExperimentSpec(spec_id="s1", hypothesis="H")
        d = spec.to_dict()
        assert d["spec_id"] == "s1"
        assert "hypothesis" in d

    def test_experiment_result(self):
        from research_engine.experiments.experiment_spec import ExperimentResult

        r = ExperimentResult(spec_id="s1", success=True, confidence=0.8)
        assert r.success is True
        assert r.to_dict()["confidence"] == 0.8


class TestExperimentRunner:
    def test_run_unknown_executor(self):
        from research_engine.experiments.experiment_runner import ExperimentRunner
        from research_engine.experiments.experiment_spec import ExperimentSpec

        runner = ExperimentRunner()
        spec = ExperimentSpec(hypothesis="test")
        result = runner.run(spec)
        assert result.success is False
        assert "No executor" in result.error

    def test_run_registered_executor(self):
        from research_engine.experiments.experiment_runner import ExperimentRunner
        from research_engine.experiments.experiment_spec import ExperimentSpec

        runner = ExperimentRunner()
        runner.register_executor("default", lambda s: {"metrics": {"acc": 0.9}, "confidence": 0.85})
        spec = ExperimentSpec(hypothesis="test")
        result = runner.run(spec)
        assert result.success is True
        assert result.confidence == 0.85

    def test_run_executor_exception(self):
        from research_engine.experiments.experiment_runner import ExperimentRunner
        from research_engine.experiments.experiment_spec import ExperimentSpec

        runner = ExperimentRunner()
        runner.register_executor("default", lambda s: (_ for _ in ()).throw(ValueError("boom")))
        spec = ExperimentSpec(hypothesis="test")
        result = runner.run(spec)
        assert result.success is False
        assert "boom" in result.error


class TestExperimentScheduler:
    def test_submit_and_next(self):
        from research_engine.experiments.experiment_scheduler import ExperimentScheduler
        from research_engine.experiments.experiment_spec import ExperimentSpec

        sched = ExperimentScheduler()
        spec = ExperimentSpec(hypothesis="H")
        item = sched.submit(spec)
        assert item.status == "queued"
        assert sched.pending_count() == 1

        got = sched.next()
        assert got is not None
        assert got.status == "running"
        assert sched.running_count() == 1

        sched.complete(got)
        assert got.status == "completed"
        assert sched.running_count() == 0

    def test_next_empty(self):
        from research_engine.experiments.experiment_scheduler import ExperimentScheduler

        sched = ExperimentScheduler()
        assert sched.next() is None


class TestResultEvaluator:
    def test_evaluate_success_above_threshold(self):
        from research_engine.experiments.result_evaluator import ResultEvaluator
        from research_engine.experiments.experiment_spec import ExperimentResult

        ev = ResultEvaluator(confidence_threshold=0.6)
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.8)
        verdict = ev.evaluate(result)
        assert verdict["verdict"] == "supports"

    def test_evaluate_success_below_threshold(self):
        from research_engine.experiments.result_evaluator import ResultEvaluator
        from research_engine.experiments.experiment_spec import ExperimentResult

        ev = ResultEvaluator(confidence_threshold=0.6)
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.3)
        verdict = ev.evaluate(result)
        assert verdict["verdict"] == "weak_support"

    def test_evaluate_failure(self):
        from research_engine.experiments.result_evaluator import ResultEvaluator
        from research_engine.experiments.experiment_spec import ExperimentResult

        ev = ResultEvaluator()
        result = ExperimentResult(spec_id="s1", success=False, error="timeout")
        verdict = ev.evaluate(result)
        assert verdict["verdict"] == "inconclusive"


# ── Phase 8: Conflict Detection ──────────────────────────────────────


class TestConflictDetector:
    def test_detect_from_edges(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        from research_engine.analysis.conflicts.conflict_detector import ConflictDetector

        store = GraphStore()
        store.add_node(NodeType.CLAIM, "Earth is flat", node_id="c1")
        store.add_node(NodeType.CLAIM, "Earth is round", node_id="c2")
        store.add_edge(EdgeType.CONTRADICTS, "c1", "c2")

        detector = ConflictDetector()
        conflicts = detector.detect_from_edges(store)
        assert len(conflicts) == 1
        assert conflicts[0].claim_a_id == "c1"
        assert conflicts[0].claim_b_id == "c2"

    def test_detect_by_polarity(self):
        from research_engine.analysis.conflicts.conflict_detector import ConflictDetector

        detector = ConflictDetector()
        claims = [
            {"id": "a", "subject": "gravity", "polarity": "positive"},
            {"id": "b", "subject": "gravity", "polarity": "negative"},
        ]
        conflicts = detector.detect_by_polarity(claims)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "polarity_contradiction"


class TestConflictClusters:
    def test_cluster_shared_claims(self):
        from research_engine.analysis.conflicts.conflict_detector import Conflict
        from research_engine.analysis.conflicts.conflict_clusters import ConflictClusterer

        conflicts = [
            Conflict(claim_a_id="a", claim_b_id="b"),
            Conflict(claim_a_id="b", claim_b_id="c"),
            Conflict(claim_a_id="x", claim_b_id="y"),
        ]
        clusterer = ConflictClusterer()
        clusters = clusterer.cluster(conflicts)
        assert len(clusters) == 2
        sizes = sorted(len(c) for c in clusters)
        assert sizes == [1, 2]

    def test_empty_conflicts(self):
        from research_engine.analysis.conflicts.conflict_clusters import ConflictClusterer

        assert ConflictClusterer().cluster([]) == []


class TestConflictResolver:
    def test_resolve_prefer_a(self):
        from research_engine.analysis.conflicts.conflict_detector import Conflict
        from research_engine.analysis.conflicts.conflict_resolver import ConflictResolver

        conflict = Conflict(claim_a_id="a", claim_b_id="b")
        resolver = ConflictResolver()
        res = resolver.resolve_by_confidence(conflict, 0.9, 0.3)
        assert res.action == "prefer_a"
        assert res.winning_claim_id == "a"

    def test_resolve_escalate(self):
        from research_engine.analysis.conflicts.conflict_detector import Conflict
        from research_engine.analysis.conflicts.conflict_resolver import ConflictResolver

        conflict = Conflict(claim_a_id="a", claim_b_id="b")
        resolver = ConflictResolver()
        res = resolver.resolve_by_confidence(conflict, 0.5, 0.45)
        assert res.action == "escalate"


class TestHypothesisGenerator:
    def test_from_conflict(self):
        from research_engine.analysis.conflicts.conflict_detector import Conflict
        from research_engine.analysis.hypotheses.hypothesis_generator import HypothesisGenerator

        gen = HypothesisGenerator()
        conflict = Conflict(claim_a_id="a", claim_b_id="b")
        hyp = gen.from_conflict(conflict)
        assert hyp.hypothesis_id
        assert "methodological" in hyp.text.lower()

    def test_from_evidence_gap(self):
        from research_engine.analysis.hypotheses.hypothesis_generator import HypothesisGenerator

        gen = HypothesisGenerator()
        hyp = gen.from_evidence_gap("c1", "no supporting data")
        assert hyp.source_type == "evidence_gap"
        assert "c1" in hyp.source_ids


# ── Phase 9: Retrieval System ────────────────────────────────────────


class TestEmbeddingModel:
    def test_embed_deterministic(self):
        from research_engine.retrieval.embedding_model import EmbeddingModel

        model = EmbeddingModel(dim=64)
        v1 = model.embed("hello")
        v2 = model.embed("hello")
        assert v1 == v2
        assert len(v1) == 64

    def test_similarity(self):
        from research_engine.retrieval.embedding_model import EmbeddingModel

        model = EmbeddingModel()
        v1 = model.embed("cat")
        sim = model.similarity(v1, v1)
        assert abs(sim - 1.0) < 0.01


class TestVectorIndex:
    def test_add_and_search(self):
        from research_engine.retrieval.vector_index import VectorIndex

        idx = VectorIndex()
        idx.add("d1", "machine learning algorithms")
        idx.add("d2", "quantum computing basics")
        assert idx.count() == 2

        results = idx.search("machine learning", top_k=1)
        assert len(results) == 1
        assert results[0][0] == "d1"

    def test_get_entry(self):
        from research_engine.retrieval.vector_index import VectorIndex

        idx = VectorIndex()
        idx.add("d1", "hello world", metadata={"source": "test"})
        entry = idx.get("d1")
        assert entry is not None
        assert entry.metadata["source"] == "test"


class TestSearchEngine:
    def test_add_and_search(self):
        from research_engine.retrieval.search_engine import SearchEngine

        engine = SearchEngine()
        engine.add_document("d1", "neural networks")
        engine.add_document("d2", "graph databases")
        results = engine.search("neural", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "d1"
        assert "score" in results[0]


# ── Phase 10: Operator Evolution ─────────────────────────────────────


class TestCanonicalOperatorRegistry:
    def test_register_and_get(self):
        from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry

        reg = VersionedOperatorRegistry()
        v = reg.register("extractor", "v1")
        assert v.family == "extractor"
        assert v.is_active is True

        got = reg.get("extractor")
        assert got is not None
        assert got.version == "v1"

    def test_multiple_versions(self):
        from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry

        reg = VersionedOperatorRegistry()
        reg.register("extractor", "v1")
        reg.register("extractor", "v2")
        versions = reg.list_versions("extractor")
        assert len(versions) == 2
        assert reg.active_version("extractor") == "v1"  # first auto-activated

    def test_set_active(self):
        from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry

        reg = VersionedOperatorRegistry()
        reg.register("op", "v1")
        reg.register("op", "v2")
        reg.set_active("op", "v2")
        assert reg.active_version("op") == "v2"


class TestCanonicalOperatorMetrics:
    def test_record_and_retrieve(self):
        from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore

        store = OperatorMetricsStore()
        store.record("op1", success=True, confidence=0.9, runtime=1.0)
        store.record("op1", success=False, confidence=0.2, runtime=2.0, failure_reason="timeout")
        m = store.get_metrics("op1")
        assert m is not None
        assert m.total_runs == 2
        assert m.success_rate == 0.5

    def test_underperforming(self):
        from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore

        store = OperatorMetricsStore()
        store.record("good", success=True)
        store.record("bad", success=False)
        bad = store.underperforming(threshold=0.6)
        assert len(bad) == 1
        assert bad[0].operator_name == "bad"


class TestCanonicalOperatorEvaluator:
    def test_evaluate_operator(self):
        from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore
        from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator

        store = OperatorMetricsStore()
        store.record("fam:v1", success=True, confidence=0.9, runtime=0.5)
        store.record("fam:v1", success=True, confidence=0.8, runtime=0.6)
        evaluator = OperatorEvaluator(store)
        result = evaluator.evaluate_operator("fam", "v1")
        assert result.composite_score > 0
        assert result.run_count == 2


class TestCanonicalOperatorSelector:
    def test_select_best_no_data(self):
        from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry
        from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore
        from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator
        from research_engine.operators.evolution.operator_selector import OperatorSelector

        reg = VersionedOperatorRegistry()
        reg.register("op", "v1")
        store = OperatorMetricsStore()
        evaluator = OperatorEvaluator(store)
        selector = OperatorSelector(reg, evaluator)
        result = selector.select_best("op")
        assert result.selected_version in ("v1", "")


# ── Phase 11: Reflection Layer ───────────────────────────────────────


class TestCritiqueEngine:
    def test_check_evidence_sufficiency(self):
        from research_engine.reflection.critique_engine import CritiqueEngine

        engine = CritiqueEngine()
        result = engine.check_evidence_sufficiency(3, min_evidence=2)
        assert result["passed"] is True
        result = engine.check_evidence_sufficiency(1, min_evidence=2)
        assert result["passed"] is False

    def test_critique_report(self):
        from research_engine.reflection.critique_engine import CritiqueEngine

        engine = CritiqueEngine()
        checks = [
            engine.check_logical_consistency(["p1"], "c1"),
            engine.check_evidence_sufficiency(0),
        ]
        report = engine.critique("claim_1", checks)
        assert report.passed is False
        assert len(report.issues) == 1


class TestErrorClassifier:
    def test_classify_known_pattern(self):
        from research_engine.reflection.error_classifier import ErrorClassifier, ErrorCategory

        classifier = ErrorClassifier()
        result = classifier.classify("confidence too low", source="test")
        assert result.category == ErrorCategory.CONFIDENCE

    def test_classify_unknown(self):
        from research_engine.reflection.error_classifier import ErrorClassifier, ErrorCategory

        classifier = ErrorClassifier()
        result = classifier.classify("something weird happened")
        assert result.category == ErrorCategory.UNKNOWN


class TestReflectionLoop:
    def test_run_cycles(self):
        from research_engine.reflection.reflection_loop import ReflectionLoop

        loop = ReflectionLoop()
        loop.run_cycle(["obs1"], ["act1"], score=0.8)
        loop.run_cycle(["obs2"], ["act2"], score=0.6)
        assert loop.cycle_count == 2
        assert abs(loop.average_quality() - 0.7) < 0.01

    def test_recent_entries(self):
        from research_engine.reflection.reflection_loop import ReflectionLoop

        loop = ReflectionLoop()
        for i in range(10):
            loop.run_cycle([f"obs{i}"], [f"act{i}"], score=float(i))
        recent = loop.recent_entries(3)
        assert len(recent) == 3
        assert recent[-1].cycle_id == 10


# ── Phase 12: Multi-Agent Framework ─────────────────────────────────


class TestCanonicalAgentProtocol:
    def test_request_types(self):
        from research_engine.agents.core.agent_protocol import RequestType

        assert RequestType.TASK_PROPOSAL.value == "task_proposal"
        assert RequestType.EXECUTION_REQUEST.value == "execution_request"

    def test_validate_request(self):
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType, validate_request

        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="agent1",
            task_type="plan",
        )
        valid, reason = validate_request(req)
        assert valid is True

    def test_check_forbidden(self):
        from research_engine.agents.core.agent_protocol import check_forbidden

        assert check_forbidden("graph.add_node") is True
        assert check_forbidden("read_data") is False


class TestCanonicalAgentRouter:
    def test_route_to_agent(self):
        from research_engine.agents.core.agent_registry import AgentRegistry
        from research_engine.agents.core.agent_router import AgentRouter
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType
        from research_engine.agents.core.reader_agent import ReaderAgent

        registry = AgentRegistry()
        reader = ReaderAgent()
        registry.register(reader)

        router = AgentRouter(registry)
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="test",
            task_type="extract_claims",
            payload={"text": "Neural networks are powerful. They can learn complex patterns from data."},
        )
        result = router.route(req)
        assert result.routed is True
        assert result.response is not None
        assert result.response.success is True

    def test_route_no_handler(self):
        from research_engine.agents.core.agent_registry import AgentRegistry
        from research_engine.agents.core.agent_router import AgentRouter
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        router = AgentRouter(AgentRegistry())
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="test",
            task_type="nonexistent_task",
        )
        result = router.route(req)
        assert result.routed is False


# ── Phase 13: First Agent Set ────────────────────────────────────────


class TestCanonicalPlannerAgent:
    def test_plan_next_action(self):
        from research_engine.agents.core.planner_agent import PlannerAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = PlannerAgent()
        assert agent.can_handle("plan_next_action")
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="test",
            task_type="plan_next_action",
            payload={"open_hypotheses": 3, "unresolved_conflicts": 1},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert "action" in resp.result


class TestCanonicalReaderAgent:
    def test_extract_claims(self):
        from research_engine.agents.core.reader_agent import ReaderAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = ReaderAgent()
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="test",
            task_type="extract_claims",
            payload={"text": "Neural networks can learn complex patterns. They require large datasets for training."},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert resp.result["count"] >= 1


class TestCanonicalEvidenceAgent:
    def test_search_evidence(self):
        from research_engine.agents.core.evidence_agent import EvidenceAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = EvidenceAgent()
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="test",
            task_type="search_evidence",
            payload={"claim_id": "c1", "query": "neural networks"},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert resp.result["search_performed"] is True


class TestCanonicalCriticAgent:
    def test_critique_claim(self):
        from research_engine.agents.core.critic_agent import CriticAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = CriticAgent()
        req = AgentRequest(
            request_type=RequestType.CRITIQUE_REQUEST,
            source_agent="test",
            task_type="critique_claim",
            payload={"claim": {"text": "A claim", "confidence": 0.9, "source": "paper"}},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert "recommendation" in resp.result


# ── Phase 14: Second Agent Set ───────────────────────────────────────


class TestCanonicalTheoryAgent:
    def test_generate_hypothesis(self):
        from research_engine.agents.core.theory_agent import TheoryAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = TheoryAgent()
        req = AgentRequest(
            request_type=RequestType.ARTIFACT_PROPOSAL,
            source_agent="test",
            task_type="generate_hypothesis",
            payload={"claims": [{"text": "A claim"}], "context": "ML"},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert "hypothesis" in resp.result


class TestCanonicalExperimentAgent:
    def test_design_experiment(self):
        from research_engine.agents.core.experiment_agent import ExperimentAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = ExperimentAgent()
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="test",
            task_type="design_experiment",
            payload={"hypothesis": "test hypothesis"},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert resp.result["status"] == "designed"


class TestCanonicalSynthesisAgent:
    def test_generate_report(self):
        from research_engine.agents.core.synthesis_agent import SynthesisAgent
        from research_engine.agents.core.agent_protocol import AgentRequest, RequestType

        agent = SynthesisAgent()
        req = AgentRequest(
            request_type=RequestType.ARTIFACT_PROPOSAL,
            source_agent="test",
            task_type="generate_report",
            payload={"title": "Test Report", "claims": [{"text": "Finding 1", "confidence": 0.9}]},
        )
        resp = agent.execute_request(req)
        assert resp.success is True
        assert "report" in resp.result
        assert "Test Report" in resp.result["report"]


# ── Phase 15: Sandbox ────────────────────────────────────────────────


class TestCanonicalSandbox:
    def test_allowed_code(self):
        from research_engine.sandbox.sandbox_runtime import SandboxRuntime

        runtime = SandboxRuntime()
        result = runtime.execute("print('hello')")
        assert result.success is True

    def test_blocked_code(self):
        from research_engine.sandbox.sandbox_runtime import SandboxRuntime

        runtime = SandboxRuntime()
        result = runtime.execute("import os; os.system('rm -rf /')")
        assert result.success is False
        assert "security policy" in result.error.lower()

    def test_resource_limits(self):
        from research_engine.sandbox.resource_limits import ResourceLimits

        limits = ResourceLimits(cpu_seconds=10, memory_mb=128)
        assert limits.cpu_seconds == 10
        assert limits.to_dict()["memory_mb"] == 128

    def test_security_policy(self):
        from research_engine.sandbox.security_policy import SecurityPolicy

        policy = SecurityPolicy()
        assert policy.is_allowed("x = 1 + 2") is True
        assert policy.is_allowed("import subprocess") is False


# ── Phase 16: API Server ─────────────────────────────────────────────


class TestCanonicalAPIServer:
    def test_register_and_handle(self):
        from research_engine.api.server import ResearchAPIServer

        server = ResearchAPIServer()
        server.register_route("/test", lambda p: {"echo": p.get("msg", "")})

        resp = server.handle("/test", {"msg": "hello"})
        assert resp.success is True
        assert resp.data["echo"] == "hello"

    def test_route_not_found(self):
        from research_engine.api.server import ResearchAPIServer

        server = ResearchAPIServer()
        resp = server.handle("/missing")
        assert resp.success is False
        assert "not found" in resp.error.lower()

    def test_handler_exception(self):
        from research_engine.api.server import ResearchAPIServer

        def bad_handler(p):
            raise ValueError("oops")

        server = ResearchAPIServer()
        server.register_route("/bad", bad_handler)
        resp = server.handle("/bad")
        assert resp.success is False
        assert "oops" in resp.error


# ── Phase 2: Executor Flow (tests/runtime/test_executor_flow.py equivalent) ──


class TestExecutorFlow:
    """End-to-end executor pipeline test as specified in Phase 2."""

    def test_full_pipeline(self):
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
        from research_engine.core.runtime.artifact_validator import ArtifactValidator
        from research_engine.core.runtime.postcondition_verifier import PostconditionVerifier
        from research_engine.core.runtime.verified_executor import VerifiedExecutor

        registry = RunRegistry()
        validator = ArtifactValidator()
        verifier = PostconditionVerifier()
        executor = VerifiedExecutor(registry, validator, verifier)

        def my_operator(inputs):
            return {
                "artifacts": [
                    {
                        "id": "a1",
                        "type": "normalized_claim_set",
                        "data": {
                            "claims": [
                                {"text": "Test claim", "confidence": 0.8, "provenance": "test"}
                            ]
                        },
                    }
                ]
            }

        result = executor.execute(my_operator, {"text": "input"}, operator_name="test_op")
        run = registry.list_runs()[-1]
        assert run.status == RunStatus.VERIFIED_SUCCESS


# ── End-to-end integration: First Working Milestone ──────────────────


class TestFirstWorkingMilestone:
    """Demonstrates the full research loop from the upgrade plan."""

    def test_claim_to_belief_revision_loop(self):
        """
        claim extracted → artifact created → artifact validated →
        claim stored in graph → evidence added → contradiction detected →
        hypothesis generated → experiment executed → belief revision recorded →
        planner schedules next action
        """
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        from research_engine.graph.temporal.version_tracker import VersionTracker
        from research_engine.graph.temporal.temporal_graph import TemporalGraph
        from research_engine.graph.temporal.belief_timeline import BeliefTimeline
        from research_engine.core.runtime.artifact_validator import ArtifactValidator
        from research_engine.core.artifacts.artifact_schema import Artifact
        from research_engine.core.artifacts.artifact_store import ArtifactStore
        from research_engine.analysis.conflicts.conflict_detector import ConflictDetector
        from research_engine.analysis.hypotheses.hypothesis_generator import HypothesisGenerator
        from research_engine.experiments.experiment_spec import ExperimentSpec, ExperimentResult
        from research_engine.experiments.experiment_runner import ExperimentRunner
        from research_engine.experiments.result_evaluator import ResultEvaluator
        from research_engine.planner.research_planner import ResearchPlanner, PlannerState

        # 1. Set up infrastructure
        graph = GraphStore()
        tracker = VersionTracker()
        temporal = TemporalGraph(graph, tracker)
        timeline = BeliefTimeline(tracker)
        validator = ArtifactValidator()
        artifact_store = ArtifactStore()

        # 2. Reader extracts claim → artifact created
        claim_data = {"claims": [{"text": "Neural networks scale well", "confidence": 0.8, "provenance": "paper_1"}]}
        validation = validator.validate("art_1", "normalized_claim_set", claim_data)
        assert validation.valid is True

        artifact = Artifact(artifact_id="art_1", artifact_type="normalized_claim_set", data=claim_data, producer_run="run_1")
        artifact_store.store(artifact)

        # 3. Claim stored in graph
        claim_node = graph.add_node(NodeType.CLAIM, "Neural networks scale well", metadata={"confidence": 0.8})
        claim_node_id = claim_node.node_id

        # 4. Create initial belief revision
        rev = tracker.create_revision("claim", claim_node_id, {"confidence": 0.8, "text": "Neural networks scale well"}, cause="initial_extraction")

        # 5. Add evidence
        evidence_node = graph.add_node(NodeType.EVIDENCE, "Paper X shows scaling", metadata={"strength": 0.7})
        graph.add_edge(EdgeType.SUPPORTS, evidence_node.node_id, claim_node_id)

        # 6. Add contradicting claim
        contra_node = graph.add_node(NodeType.CLAIM, "Neural networks hit scaling walls", metadata={"confidence": 0.6})
        contra_node_id = contra_node.node_id
        graph.add_edge(EdgeType.CONTRADICTS, claim_node_id, contra_node_id)

        # 7. Detect contradiction
        detector = ConflictDetector()
        conflicts = detector.detect_from_edges(graph)
        assert len(conflicts) >= 1

        # 8. Generate hypothesis
        generator = HypothesisGenerator()
        hypothesis = generator.from_conflict(conflicts[0])
        assert hypothesis.hypothesis_id
        graph.add_node(NodeType.HYPOTHESIS, hypothesis.text)

        # 9. Run experiment
        runner = ExperimentRunner()
        runner.register_executor("default", lambda s: {"metrics": {"accuracy": 0.85}, "confidence": 0.75})
        spec = ExperimentSpec(hypothesis=hypothesis.text)
        result = runner.run(spec)
        assert result.success is True

        # 10. Evaluate result
        evaluator = ResultEvaluator()
        verdict = evaluator.evaluate(result)
        assert verdict["verdict"] in ("supports", "weak_support")

        # 11. Record belief revision
        new_confidence = 0.65 if verdict["verdict"] == "weak_support" else 0.85
        rev2 = tracker.create_revision(
            "claim", claim_node_id,
            {"confidence": new_confidence, "text": "Neural networks scale well"},
            cause=f"experiment_{spec.spec_id}",
            previous_version=rev.version,
        )
        assert tracker.revision_count("claim", claim_node_id) == 2

        # 12. Planner schedules next action
        planner = ResearchPlanner()
        state = PlannerState(
            open_hypotheses=1,
            unresolved_conflicts=1,
            untested_claims=0,
            evidence_gaps=1,
        )
        action = planner.select_action(state)
        assert action  # planner returns a non-empty action

        # Full loop complete!
        assert graph.node_count >= 4  # claim, evidence, contra-claim, hypothesis
        assert graph.edge_count >= 2  # supports, contradicts
