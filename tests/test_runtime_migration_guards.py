"""Migration guard tests — high-level checks that critical paths survive refactoring.

These tests verify that the canonical runtime boundary remains functional
throughout the migration.  They must pass at every commit on the
runtime-unification branch.
"""
from __future__ import annotations

import pytest


class TestBackendDelegatesToCanonicalExecutor:
    """Verify that backend execution uses canonical runtime modules."""

    def test_canonical_run_registry_importable(self):
        from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
        reg = RunRegistry()
        run = reg.create_run(operator_name="guard_op", inputs={"x": 1})
        assert run.status == RunStatus.PENDING

    def test_canonical_artifact_validator_importable(self):
        from research_engine.core.runtime.artifact_validator import ArtifactValidator
        v = ArtifactValidator()
        result = v.validate("a1", "unknown_type", {"key": "val"})
        assert result.valid  # unknown types pass with warning

    def test_canonical_postcondition_verifier_importable(self):
        from research_engine.core.runtime.postcondition_verifier import PostconditionVerifier
        pv = PostconditionVerifier()
        report = pv.verify("some_op", {}, {"artifacts": []})
        assert report.all_passed  # no postconditions registered

    def test_canonical_verified_executor_importable(self):
        from research_engine.core.runtime.verified_executor import VerifiedExecutor
        executor = VerifiedExecutor()
        assert executor is not None


class TestArtifactCreationStillWorks:
    """Verify that the canonical artifact subsystem is functional."""

    def test_artifact_schema_creation(self):
        from research_engine.core.artifacts.artifact_schema import Artifact
        a = Artifact(artifact_type="test", data={"text": "hello"})
        assert a.artifact_id
        assert a.artifact_type == "test"

    def test_artifact_store_roundtrip(self):
        from research_engine.core.artifacts.artifact_store import ArtifactStore
        from research_engine.core.artifacts.artifact_schema import Artifact
        store = ArtifactStore()
        a = Artifact(artifact_type="claim", data={"text": "test"})
        store.store(a)
        fetched = store.get(a.artifact_id)
        assert fetched is not None
        assert fetched.artifact_type == "claim"

    def test_artifact_indexer(self):
        from research_engine.core.artifacts.artifact_indexer import ArtifactIndexer
        from research_engine.core.artifacts.artifact_schema import Artifact
        indexer = ArtifactIndexer()
        a = Artifact(artifact_type="evidence", data={})
        indexer.index(a)
        assert a.artifact_id in indexer.lookup_by_type("evidence")

    def test_artifact_sideeffect_processor(self):
        from research_engine.core.artifacts.artifact_sideeffects import SideEffectProcessor
        proc = SideEffectProcessor()
        assert proc is not None


class TestGraphUpdatesStillWork:
    """Verify that the canonical graph store is functional."""

    def test_graph_store_add_and_query_nodes(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        gs = GraphStore()
        node = gs.add_node(NodeType.CLAIM, {"text": "test claim"})
        assert gs.node_count == 1
        found = gs.query_nodes(node_type=NodeType.CLAIM)
        assert len(found) == 1
        assert found[0].node_id == node.node_id

    def test_graph_store_add_and_query_edges(self):
        from research_engine.graph.graph_store import GraphStore
        from research_engine.graph.node_types import NodeType
        from research_engine.graph.edge_types import EdgeType
        gs = GraphStore()
        n1 = gs.add_node(NodeType.CLAIM, {"text": "claim 1"})
        n2 = gs.add_node(NodeType.EVIDENCE, {"text": "evidence 1"})
        edge = gs.add_edge(EdgeType.SUPPORTS, n1.node_id, n2.node_id)
        assert gs.edge_count == 1
        found = gs.query_edges(edge_type=EdgeType.SUPPORTS)
        assert len(found) == 1
        assert found[0].edge_id == edge.edge_id


class TestOperatorRegistryStillLoads:
    """Verify that operator registries load correctly."""

    def test_canonical_operator_registry_importable(self):
        from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry
        reg = VersionedOperatorRegistry()
        assert reg is not None

    def test_operator_evaluator_importable(self):
        from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator
        from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore
        store = OperatorMetricsStore()
        ev = OperatorEvaluator(store)
        assert ev is not None


class TestSandboxEntrypointRemains:
    """Verify that sandbox execution is available."""

    def test_sandbox_runtime_importable(self):
        from research_engine.sandbox.sandbox_runtime import SandboxRuntime
        rt = SandboxRuntime()
        assert rt is not None

    def test_sandbox_execute_stub(self):
        from research_engine.sandbox.sandbox_runtime import SandboxRuntime
        rt = SandboxRuntime()
        result = rt.execute("print('hello')")
        assert result.success is True


class TestRuntimeContextAndExecutor:
    """Verify the new canonical runtime entrypoint modules."""

    def test_runtime_context_importable(self):
        from research_engine.core.runtime.runtime_context import RuntimeContext
        ctx = RuntimeContext(
            active_node="node-1",
            project_id="proj-1",
            operator_name="researcher",
        )
        assert ctx.active_node == "node-1"
        assert ctx.run_id  # auto-generated

    def test_execution_result_importable(self):
        from research_engine.core.runtime.execution_result import ExecutionResult
        result = ExecutionResult(status="success", run_id="r1")
        assert result.status == "success"
        assert result.to_dict()["run_id"] == "r1"

    def test_executor_importable(self):
        from research_engine.core.runtime.executor import CanonicalExecutor
        executor = CanonicalExecutor()
        assert executor is not None

    def test_executor_run_node(self):
        from research_engine.core.runtime.executor import CanonicalExecutor
        from research_engine.core.runtime.runtime_context import RuntimeContext

        def simple_op(inputs):
            return {
                "artifacts": [{
                    "id": "a1",
                    "type": "unknown_type",
                    "data": {"text": "result"},
                }]
            }

        executor = CanonicalExecutor()
        executor.register_operator("simple_op", simple_op)
        ctx = RuntimeContext(
            active_node="n1",
            project_id="p1",
            operator_name="simple_op",
        )
        result = executor.run_node(ctx)
        assert result.status == "success"
        assert result.run_id
        assert len(result.artifacts) == 1
