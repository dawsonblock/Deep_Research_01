"""Temporal instability scorer — scores knowledge instability for planner prioritization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_engine.graph.graph_store import GraphStore
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType
from research_engine.graph.temporal.version_tracker import VersionTracker
from research_engine.graph.temporal.belief_timeline import BeliefTimeline


@dataclass
class InstabilityReport:
    """Summary of knowledge instability across the graph."""
    contradiction_density: float = 0.0
    unsupported_claims: int = 0
    open_hypotheses: int = 0
    revision_churn: float = 0.0
    weakening_trends: int = 0
    unstable_theories: int = 0

    @property
    def total_score(self) -> float:
        """Weighted instability score.  Higher = more unstable."""
        return (
            self.contradiction_density * 3.0
            + self.unsupported_claims * 1.0
            + self.open_hypotheses * 0.5
            + self.revision_churn * 2.0
            + self.weakening_trends * 2.5
            + self.unstable_theories * 2.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_density": self.contradiction_density,
            "unsupported_claims": self.unsupported_claims,
            "open_hypotheses": self.open_hypotheses,
            "revision_churn": self.revision_churn,
            "weakening_trends": self.weakening_trends,
            "unstable_theories": self.unstable_theories,
            "total_score": self.total_score,
        }


class InstabilityScorer:
    """Scores the current knowledge graph for instability.

    Used by the planner to prioritize work on unstable or under-supported
    knowledge rather than following fixed task sequences.
    """

    def __init__(
        self,
        store: GraphStore,
        tracker: VersionTracker | None = None,
        timeline: BeliefTimeline | None = None,
    ) -> None:
        self.store = store
        self.tracker = tracker
        self.timeline = timeline

    def score(self) -> InstabilityReport:
        report = InstabilityReport()
        report.contradiction_density = self._contradiction_density()
        report.unsupported_claims = self._unsupported_claims()
        report.open_hypotheses = self._open_hypotheses()
        if self.tracker is not None:
            report.revision_churn = self._revision_churn()
        if self.timeline is not None:
            report.weakening_trends = self._weakening_trends()
        report.unstable_theories = self._unstable_theories()
        return report

    # ── metrics ──────────────────────────────────────────────────────

    def _contradiction_density(self) -> float:
        """Fraction of edges that are contradictions."""
        all_edges = self.store.query_edges()
        if not all_edges:
            return 0.0
        contradictions = [e for e in all_edges if e.edge_type == EdgeType.CONTRADICTS]
        return len(contradictions) / len(all_edges)

    def _unsupported_claims(self) -> int:
        """Count claims with no supporting evidence edges."""
        claims = self.store.query_nodes(node_type=NodeType.CLAIM)
        count = 0
        for claim in claims:
            incoming = self.store.query_edges(target_id=claim.node_id)
            has_support = any(e.edge_type == EdgeType.SUPPORTS for e in incoming)
            if not has_support:
                count += 1
        return count

    def _open_hypotheses(self) -> int:
        """Count hypotheses not yet linked to an experiment."""
        hypotheses = self.store.query_nodes(node_type=NodeType.HYPOTHESIS)
        count = 0
        for h in hypotheses:
            outgoing = self.store.query_edges(source_id=h.node_id)
            has_test = any(e.edge_type == EdgeType.TESTS for e in outgoing)
            incoming = self.store.query_edges(target_id=h.node_id)
            has_test = has_test or any(e.edge_type == EdgeType.TESTS for e in incoming)
            if not has_test:
                count += 1
        return count

    def _revision_churn(self) -> float:
        """Average number of revisions per tracked entity (higher = more churn)."""
        if self.tracker is None:
            return 0.0
        keys = self.tracker.all_entity_keys()
        if not keys:
            return 0.0
        total_revisions = 0
        for key in keys:
            entity_type, entity_id = key.split(":", 1)
            total_revisions += self.tracker.revision_count(entity_type, entity_id)
        return total_revisions / len(keys)

    def _weakening_trends(self) -> int:
        """Count entities whose latest revision lowered confidence."""
        if self.timeline is None:
            return 0
        count = 0
        claims = self.store.query_nodes(node_type=NodeType.CLAIM)
        for claim in claims:
            tl = self.timeline.timeline_for_claim(claim.node_id)
            if len(tl) >= 2:
                if tl[-1].confidence < tl[-2].confidence:
                    count += 1
        return count

    def _unstable_theories(self) -> int:
        """Count theory nodes whose confidence changed more than twice."""
        if self.tracker is None:
            return 0
        count = 0
        theories = self.store.query_nodes(node_type=NodeType.THEORY)
        for theory in theories:
            history = self.tracker.revision_history("theory", theory.node_id)
            if len(history) > 2:
                count += 1
        return count
