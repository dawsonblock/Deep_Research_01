"""Tests for agent router."""
import pytest
from research_engine.agents.core.agent_registry import AgentRegistry
from research_engine.agents.core.agent_router import AgentRouter
from research_engine.agents.core.agent_protocol import AgentRequest, RequestType
from research_lab.agents.reader.reader_agent import ReaderAgent
from research_lab.agents.evidence.evidence_agent import EvidenceAgent
from research_lab.agents.critic.critic_agent import CriticAgent
from research_lab.agents.planner.planner_agent import PlannerAgent


class TestAgentRouter:
    def setup_method(self):
        self.registry = AgentRegistry()
        self.router = AgentRouter(self.registry)
        # Register agents
        self.registry.register(ReaderAgent())
        self.registry.register(EvidenceAgent())
        self.registry.register(CriticAgent())
        self.registry.register(PlannerAgent())

    def test_route_to_reader(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="extract_claims",
            payload={"text": "This is a test paper about climate change impacts on agriculture.", "source": "test"},
        )
        result = self.router.route(req)
        assert result.routed is True
        assert result.agent_id == "reader_agent"
        assert result.response is not None
        assert result.response.success is True

    def test_route_to_evidence(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="search_evidence",
            payload={"claim_id": "c1", "query": "climate change"},
        )
        result = self.router.route(req)
        assert result.routed is True
        assert result.agent_id == "evidence_agent"

    def test_route_to_critic(self):
        req = AgentRequest(
            request_type=RequestType.CRITIQUE_REQUEST,
            source_agent="planner",
            task_type="critique_claim",
            payload={"claim": {"text": "test claim", "confidence": 0.2, "id": "c1"}},
        )
        result = self.router.route(req)
        assert result.routed is True
        assert result.agent_id == "critic_agent"

    def test_route_to_planner(self):
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="system",
            task_type="plan_next_action",
            payload={"evidence_gaps": 3},
        )
        result = self.router.route(req)
        assert result.routed is True
        assert result.agent_id == "planner_agent"

    def test_route_unknown_task(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="nonexistent_task",
        )
        result = self.router.route(req)
        assert result.routed is False

    def test_route_invalid_request(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="",
            task_type="extract_claims",
        )
        result = self.router.route(req)
        assert result.routed is False

    def test_route_to_specific_agent(self):
        req = AgentRequest(
            request_type=RequestType.CRITIQUE_REQUEST,
            source_agent="planner",
            task_type="critique_claim",
            payload={"claim": {"text": "test", "confidence": 0.9}},
        )
        result = self.router.route_to_specific("critic_agent", req)
        assert result.routed is True
        assert result.agent_id == "critic_agent"

    def test_routing_history(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="extract_claims",
            payload={"text": "Testing routing history with sufficient text content.", "source": "test"},
        )
        self.router.route(req)
        assert len(self.router.routing_history) == 1

    def test_multi_agent_parallel_tasks(self):
        """Test that different task types route to different agents."""
        reader_req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="extract_claims",
            payload={"text": "Climate change affects agriculture in many regions worldwide.", "source": "test"},
        )
        evidence_req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="planner",
            task_type="search_evidence",
            payload={"claim_id": "c1"},
        )
        r1 = self.router.route(reader_req)
        r2 = self.router.route(evidence_req)
        assert r1.agent_id == "reader_agent"
        assert r2.agent_id == "evidence_agent"
        assert r1.routed and r2.routed
