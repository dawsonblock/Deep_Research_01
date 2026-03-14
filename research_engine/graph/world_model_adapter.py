"""World model adapter — projects backend world-model state into the canonical graph."""
from __future__ import annotations

from typing import Any

from research_engine.graph.graph_store import GraphStore
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType


class WorldModelAdapter:
    """Projects backend world-model entities (claims, questions, hypotheses)
    into the canonical :class:`GraphStore`.

    This adapter is a *write-only mirror*: it copies backend data into the
    canonical graph but never reads from the graph to answer backend queries.
    """

    def __init__(self, store: GraphStore | None = None) -> None:
        self.store = store or GraphStore()

    # ── projections ──────────────────────────────────────────────────

    def mirror_claim(self, claim: dict[str, Any]) -> str:
        """Mirror a backend claim row into the canonical graph."""
        node = self.store.add_node(
            NodeType.CLAIM,
            content={"text": claim.get("content", ""), "source_artifact": claim.get("artifact_id", "")},
            node_id=claim.get("id"),
            metadata={
                "confidence": claim.get("confidence", 0.0),
                "status": claim.get("status", "active"),
                "project_id": claim.get("project_id", ""),
            },
        )
        return node.node_id

    def mirror_hypothesis(self, hypothesis: dict[str, Any]) -> str:
        """Mirror a backend hypothesis row into the canonical graph."""
        node = self.store.add_node(
            NodeType.HYPOTHESIS,
            content={
                "statement": hypothesis.get("statement", ""),
                "prediction": hypothesis.get("prediction", ""),
            },
            node_id=hypothesis.get("id"),
            metadata={
                "confidence": hypothesis.get("confidence", 0.0),
                "status": hypothesis.get("status", "active"),
                "project_id": hypothesis.get("project_id", ""),
            },
        )
        return node.node_id

    def mirror_evidence(self, evidence: dict[str, Any], claim_id: str | None = None) -> str:
        """Mirror a backend evidence item into the canonical graph."""
        node = self.store.add_node(
            NodeType.EVIDENCE,
            content={"text": evidence.get("content", evidence.get("title", ""))},
            node_id=evidence.get("id"),
            metadata={
                "confidence": evidence.get("confidence", 0.5),
                "project_id": evidence.get("project_id", ""),
            },
        )
        if claim_id:
            try:
                self.store.get_node(claim_id)
                self.store.add_edge(
                    EdgeType.SUPPORTS,
                    source_id=node.node_id,
                    target_id=claim_id,
                )
            except KeyError:
                pass
        return node.node_id

    def mirror_experiment(self, experiment: dict[str, Any]) -> str:
        """Mirror a backend experiment into the canonical graph."""
        node = self.store.add_node(
            NodeType.EXPERIMENT,
            content={"description": experiment.get("description", "")},
            node_id=experiment.get("id"),
            metadata={
                "status": experiment.get("status", "pending"),
                "project_id": experiment.get("project_id", ""),
            },
        )
        return node.node_id

    def mirror_result(self, result: dict[str, Any], experiment_id: str | None = None) -> str:
        """Mirror an experiment result into the canonical graph."""
        node = self.store.add_node(
            NodeType.RESULT,
            content={"metrics": result.get("metrics", {}), "verdict": result.get("verdict", "")},
            node_id=result.get("id"),
            metadata={"project_id": result.get("project_id", "")},
        )
        if experiment_id:
            try:
                self.store.get_node(experiment_id)
                self.store.add_edge(
                    EdgeType.PRODUCED,
                    source_id=experiment_id,
                    target_id=node.node_id,
                )
            except KeyError:
                pass
        return node.node_id
