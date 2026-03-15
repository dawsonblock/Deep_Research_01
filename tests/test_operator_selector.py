"""Tests for operator selector."""
import pytest
from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry
from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore
from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator
from research_engine.operators.evolution.operator_selector import OperatorSelector


class TestOperatorSelector:
    def setup_method(self):
        self.registry = VersionedOperatorRegistry()
        self.metrics = OperatorMetricsStore()
        self.evaluator = OperatorEvaluator(self.metrics)
        self.selector = OperatorSelector(
            self.registry, self.evaluator, min_runs=3
        )

    def test_select_best_no_versions(self):
        result = self.selector.select_best("nonexistent")
        assert result.selected_version == ""

    def test_select_best_with_data(self):
        self.registry.register("extractor", "v1")
        self.registry.register("extractor", "v2")
        for _ in range(5):
            self.metrics.record("extractor:v1", success=True, confidence=0.5, runtime=2.0)
        for _ in range(5):
            self.metrics.record("extractor:v2", success=True, confidence=0.9, runtime=0.5)
        result = self.selector.select_best("extractor")
        assert result.selected_version == "v2"

    def test_promote_if_threshold_no_active(self):
        self.registry.register("extractor", "v1")
        result = self.selector.promote_if_threshold("extractor", "v1")
        assert result.promoted is True

    def test_promote_insufficient_runs(self):
        self.registry.register("extractor", "v1")
        self.registry.register("extractor", "v2")
        self.metrics.record("extractor:v2", success=True, confidence=0.9, runtime=0.1)
        result = self.selector.promote_if_threshold("extractor", "v2")
        assert result.promoted is False
        assert "runs" in result.reason

    def test_promote_success(self):
        self.registry.register("extractor", "v1")
        self.registry.register("extractor", "v2")
        for _ in range(5):
            self.metrics.record("extractor:v1", success=True, confidence=0.3, runtime=5.0)
        for _ in range(5):
            self.metrics.record("extractor:v2", success=True, confidence=0.9, runtime=0.5)
        result = self.selector.promote_if_threshold("extractor", "v2")
        assert result.promoted is True
        assert self.registry.active_version("extractor") == "v2"

    def test_promote_below_threshold_rejected(self):
        self.registry.register("extractor", "v1")
        self.registry.register("extractor", "v2")
        for _ in range(5):
            self.metrics.record("extractor:v1", success=True, confidence=0.8, runtime=1.0)
        for _ in range(5):
            self.metrics.record("extractor:v2", success=True, confidence=0.8, runtime=1.0)
        result = self.selector.promote_if_threshold("extractor", "v2")
        assert result.promoted is False
