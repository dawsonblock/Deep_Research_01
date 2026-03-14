"""Tests for agent protocol."""
import pytest
from research_lab.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
    validate_request,
    check_forbidden,
)


class TestAgentProtocol:
    def test_valid_request(self):
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="test_agent",
            task_type="extract_claims",
        )
        valid, reason = validate_request(req)
        assert valid is True

    def test_invalid_no_source(self):
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="",
            task_type="extract_claims",
        )
        valid, reason = validate_request(req)
        assert valid is False

    def test_invalid_no_task_type(self):
        req = AgentRequest(
            request_type=RequestType.TASK_PROPOSAL,
            source_agent="test_agent",
            task_type="",
        )
        valid, reason = validate_request(req)
        assert valid is False

    def test_check_forbidden_graph_mutation(self):
        assert check_forbidden("graph.add_node(...)") is True

    def test_check_forbidden_belief_update(self):
        assert check_forbidden("belief_update.apply(...)") is True

    def test_check_allowed_action(self):
        assert check_forbidden("search_evidence") is False

    def test_request_to_dict(self):
        req = AgentRequest(
            request_type=RequestType.EXECUTION_REQUEST,
            source_agent="reader",
            task_type="extract",
        )
        d = req.to_dict()
        assert d["request_type"] == "execution_request"
        assert d["source_agent"] == "reader"

    def test_response_to_dict(self):
        resp = AgentResponse(
            source_agent="critic",
            task_type="critique_claim",
            success=True,
            result={"score": 0.8},
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["result"]["score"] == 0.8
