"""Tests for the planner pipeline: proposer → critic → selector."""
from __future__ import annotations

import pytest


class TestPlannerOrchestrator:
    def test_propose(self):
        from research_engine.planner.orchestrator import PlannerOrchestrator
        from research_engine.planner.research_planner import PlannerState
        orch = PlannerOrchestrator()
        proposals = orch.propose(PlannerState())
        assert len(proposals) >= 1
        assert proposals[0].actions

    def test_select(self):
        from research_engine.planner.orchestrator import PlannerOrchestrator, PlanProposal
        orch = PlannerOrchestrator()
        proposals = [PlanProposal(plan_id="p1", actions=["a"])]
        selected = orch.select(proposals)
        assert selected is not None
        assert selected.plan_id == "p1"

    def test_plan(self):
        from research_engine.planner.orchestrator import PlannerOrchestrator
        from research_engine.planner.research_planner import PlannerState
        orch = PlannerOrchestrator()
        result = orch.plan(PlannerState())
        assert result is not None
        assert result.actions


class TestProposer:
    def test_propose_multiple(self):
        from research_engine.planner.proposer import Proposer
        from research_engine.planner.research_planner import PlannerState
        proposer = Proposer()
        proposals = proposer.propose(PlannerState(), max_proposals=3)
        assert len(proposals) == 3

    def test_propose_single(self):
        from research_engine.planner.proposer import Proposer
        from research_engine.planner.research_planner import PlannerState
        proposer = Proposer()
        proposals = proposer.propose(PlannerState(), max_proposals=1)
        assert len(proposals) == 1


class TestCritic:
    def test_score_proposal(self):
        from research_engine.planner.critic import Critic
        from research_engine.planner.orchestrator import PlanProposal
        critic = Critic()
        proposal = PlanProposal(plan_id="p1", actions=["search_evidence"])
        score = critic.score(proposal)
        assert score.plan_id == "p1"
        assert score.composite > 0

    def test_score_all(self):
        from research_engine.planner.critic import Critic
        from research_engine.planner.orchestrator import PlanProposal
        critic = Critic()
        proposals = [
            PlanProposal(plan_id="p1", actions=["search_evidence"]),
            PlanProposal(plan_id="p2", actions=["ingest_literature"]),
        ]
        scores = critic.score_all(proposals)
        assert len(scores) == 2
        # Should be sorted by composite score
        assert scores[0].composite >= scores[1].composite


class TestSelector:
    def test_select_best(self):
        from research_engine.planner.selector import Selector
        from research_engine.planner.orchestrator import PlanProposal
        from research_engine.planner.critic import PlanScore
        selector = Selector()
        proposals = [
            PlanProposal(plan_id="p1", actions=["a"]),
            PlanProposal(plan_id="p2", actions=["b"]),
        ]
        scores = [
            PlanScore(plan_id="p1", information_gain=0.5),
            PlanScore(plan_id="p2", information_gain=0.9),
        ]
        selected = selector.select(proposals, scores)
        assert selected.plan_id == "p2"

    def test_select_empty(self):
        from research_engine.planner.selector import Selector
        selector = Selector()
        assert selector.select([], []) is None


class TestAgendaManager:
    def test_plan_pipeline(self):
        from research_engine.planner.agenda_manager import AgendaManager
        from research_engine.planner.research_planner import PlannerState
        manager = AgendaManager()
        result = manager.plan(PlannerState())
        assert result is not None
        assert result.actions

    def test_record_outcome(self):
        from research_engine.planner.agenda_manager import AgendaManager
        manager = AgendaManager()
        manager.record_outcome("search_evidence", "default", True)
        record = manager.strategy_memory.get_record("search_evidence", "default")
        assert record is not None
        assert record.successes == 1


class TestCostModel:
    def test_estimate(self):
        from research_engine.planner.cost_model import CostModel
        model = CostModel()
        est = model.estimate("run_experiment")
        assert est.total == 5.0

    def test_total_cost(self):
        from research_engine.planner.cost_model import CostModel
        model = CostModel()
        total = model.total_cost(["ingest_literature", "extract_claims"])
        assert total == 3.0

    def test_unknown_action_default_cost(self):
        from research_engine.planner.cost_model import CostModel
        model = CostModel()
        est = model.estimate("unknown_action")
        assert est.total == 1.0
