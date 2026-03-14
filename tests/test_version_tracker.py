"""Tests for the temporal version tracker."""
import pytest
from research_lab.knowledge.graph.temporal.version_tracker import VersionTracker


class TestVersionTracker:
    def setup_method(self):
        self.tracker = VersionTracker()

    def test_create_first_revision(self):
        rev = self.tracker.create_revision(
            "claim", "c1", {"confidence": 0.8}, cause="initial"
        )
        assert rev.version == 1
        assert rev.previous_revision_id is None
        assert rev.state["confidence"] == 0.8

    def test_create_sequential_revisions(self):
        r1 = self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        r2 = self.tracker.create_revision("claim", "c1", {"confidence": 0.7}, cause="new_evidence")
        assert r2.version == 2
        assert r2.previous_revision_id == r1.revision_id

    def test_latest_version(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="initial")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.7}, cause="update")
        latest = self.tracker.latest_version("claim", "c1")
        assert latest is not None
        assert latest.version == 2
        assert latest.state["confidence"] == 0.7

    def test_latest_version_no_history(self):
        assert self.tracker.latest_version("claim", "nonexistent") is None

    def test_revision_history(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.3}, cause="initial")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.6}, cause="evidence_a")
        self.tracker.create_revision("claim", "c1", {"confidence": 0.9}, cause="evidence_b")
        history = self.tracker.revision_history("claim", "c1")
        assert len(history) == 3
        assert [r.version for r in history] == [1, 2, 3]

    def test_revision_history_empty(self):
        assert self.tracker.revision_history("claim", "none") == []

    def test_get_revision_by_id(self):
        rev = self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="init")
        found = self.tracker.get_revision(rev.revision_id)
        assert found is not None
        assert found.revision_id == rev.revision_id

    def test_get_revision_missing(self):
        assert self.tracker.get_revision("nonexistent") is None

    def test_revision_to_dict(self):
        rev = self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="init")
        d = rev.to_dict()
        assert d["entity_type"] == "claim"
        assert d["entity_id"] == "c1"
        assert d["version"] == 1

    def test_separate_entities_tracked_independently(self):
        self.tracker.create_revision("claim", "c1", {"confidence": 0.5}, cause="init")
        self.tracker.create_revision("theory", "t1", {"confidence": 0.3}, cause="init")
        assert len(self.tracker.revision_history("claim", "c1")) == 1
        assert len(self.tracker.revision_history("theory", "t1")) == 1
