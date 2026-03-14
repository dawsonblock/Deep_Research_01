"""Tests for the belief timeline."""
import pytest
from research_lab.knowledge.graph.temporal.version_tracker import VersionTracker
from research_lab.knowledge.graph.temporal.belief_timeline import BeliefTimeline


class TestBeliefTimeline:
    def setup_method(self):
        self.tracker = VersionTracker()
        self.timeline = BeliefTimeline(self.tracker)

    def test_timeline_for_claim(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.8}, cause="new_evidence")
        entries = self.timeline.timeline_for_claim("c1")
        assert len(entries) == 2
        assert entries[0].confidence == 0.5
        assert entries[1].confidence == 0.8

    def test_timeline_for_theory(self):
        self.tracker.create_revision("theory", "t1", {"confidence": 0.3}, cause="initial")
        entries = self.timeline.timeline_for_theory("t1")
        assert len(entries) == 1
        assert entries[0].confidence == 0.3

    def test_latest_confidence(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.9}, cause="update")
        assert self.timeline.latest_confidence("claim", "c1") == 0.9

    def test_latest_confidence_no_history(self):
        assert self.timeline.latest_confidence("claim", "nonexistent") is None

    def test_timeline_empty(self):
        entries = self.timeline.timeline_for_claim("nonexistent")
        assert entries == []

    def test_timeline_shows_cause(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.3}, cause="contradicting_evidence:e42")
        entries = self.timeline.timeline_for_claim("c1")
        assert entries[1].cause == "contradicting_evidence:e42"

    def test_timeline_entry_to_dict(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        entries = self.timeline.timeline_for_claim("c1")
        d = entries[0].to_dict()
        assert "confidence" in d
        assert "cause" in d
        assert "timestamp" in d
