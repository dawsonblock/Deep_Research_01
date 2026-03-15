"""Tests for the versioned operator registry."""
import pytest
from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry


class TestVersionedOperatorRegistry:
    def setup_method(self):
        self.registry = VersionedOperatorRegistry()

    def test_register_first_version_auto_active(self):
        entry = self.registry.register("claim_extractor", "v1")
        assert entry.is_active is True
        assert self.registry.active_version("claim_extractor") == "v1"

    def test_register_second_version_not_auto_active(self):
        self.registry.register("claim_extractor", "v1")
        entry = self.registry.register("claim_extractor", "v2")
        assert entry.is_active is False
        assert self.registry.active_version("claim_extractor") == "v1"

    def test_get_specific_version(self):
        self.registry.register("claim_extractor", "v1")
        self.registry.register("claim_extractor", "v2")
        v2 = self.registry.get("claim_extractor", "v2")
        assert v2 is not None
        assert v2.version == "v2"

    def test_get_active_version(self):
        self.registry.register("claim_extractor", "v1")
        self.registry.register("claim_extractor", "v2")
        active = self.registry.get("claim_extractor")
        assert active is not None
        assert active.version == "v1"

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_list_versions(self):
        self.registry.register("claim_extractor", "v1")
        self.registry.register("claim_extractor", "v2")
        versions = self.registry.list_versions("claim_extractor")
        assert len(versions) == 2

    def test_list_families(self):
        self.registry.register("claim_extractor", "v1")
        self.registry.register("evidence_ranker", "v1")
        families = self.registry.list_families()
        assert "claim_extractor" in families
        assert "evidence_ranker" in families

    def test_set_active(self):
        self.registry.register("claim_extractor", "v1")
        self.registry.register("claim_extractor", "v2")
        self.registry.set_active("claim_extractor", "v2")
        assert self.registry.active_version("claim_extractor") == "v2"
        v1 = self.registry.get("claim_extractor", "v1")
        assert v1 is not None and not v1.is_active

    def test_set_active_nonexistent_raises(self):
        self.registry.register("claim_extractor", "v1")
        with pytest.raises(KeyError):
            self.registry.set_active("claim_extractor", "v99")

    def test_operator_version_to_dict(self):
        entry = self.registry.register("claim_extractor", "v1", metadata={"desc": "initial"})
        d = entry.to_dict()
        assert d["family"] == "claim_extractor"
        assert d["version"] == "v1"
        assert d["is_active"] is True
