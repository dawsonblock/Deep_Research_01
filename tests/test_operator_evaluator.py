"""Tests for operator evaluator."""
import pytest
from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore
from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator


class TestOperatorEvaluator:
    def setup_method(self):
        self.store = OperatorMetricsStore()
        self.evaluator = OperatorEvaluator(self.store)

    def test_evaluate_no_data(self):
        result = self.evaluator.evaluate_operator("claim_extractor", "v1")
        assert result.composite_score == 0.0
        assert result.run_count == 0

    def test_evaluate_with_metrics(self):
        self.store.record("claim_extractor:v1", success=True, confidence=0.8, runtime=1.0)
        self.store.record("claim_extractor:v1", success=True, confidence=0.9, runtime=0.5)
        result = self.evaluator.evaluate_operator("claim_extractor", "v1")
        assert result.composite_score > 0.0
        assert result.run_count == 2

    def test_compare_versions(self):
        # v1: good success, low confidence
        for _ in range(5):
            self.store.record("claim_extractor:v1", success=True, confidence=0.5, runtime=1.0)
        # v2: good success, high confidence
        for _ in range(5):
            self.store.record("claim_extractor:v2", success=True, confidence=0.9, runtime=0.5)
        results = self.evaluator.compare_versions("claim_extractor", ["v1", "v2"])
        assert len(results) == 2
        # v2 should score higher (higher confidence, lower runtime)
        assert results[0].version == "v2"

    def test_evaluate_result_to_dict(self):
        self.store.record("claim_extractor:v1", success=True, confidence=0.7, runtime=2.0)
        result = self.evaluator.evaluate_operator("claim_extractor", "v1")
        d = result.to_dict()
        assert "composite_score" in d
        assert "metric_scores" in d
