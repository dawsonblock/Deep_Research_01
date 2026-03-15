"""Tests for the experiment feedback engine."""
from __future__ import annotations

import pytest


class TestFeedbackEngine:
    def test_process_supporting_result(self):
        from research_engine.experiments.feedback_engine import FeedbackEngine
        from research_engine.experiments.experiment_spec import ExperimentResult
        engine = FeedbackEngine()
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.9)
        report = engine.process(result)
        assert report.verdict == "supports"
        assert any(a.action_type == "update_belief" for a in report.actions)

    def test_process_weak_support(self):
        from research_engine.experiments.feedback_engine import FeedbackEngine
        from research_engine.experiments.experiment_spec import ExperimentResult
        engine = FeedbackEngine()
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.4)
        report = engine.process(result)
        assert report.verdict == "weak_support"
        assert any(a.action_type == "design_followup_experiment" for a in report.actions)

    def test_process_failed_result(self):
        from research_engine.experiments.feedback_engine import FeedbackEngine
        from research_engine.experiments.experiment_spec import ExperimentResult
        engine = FeedbackEngine()
        result = ExperimentResult(spec_id="s1", success=False, error="timeout")
        report = engine.process(result)
        assert report.verdict == "inconclusive"

    def test_low_confidence_triggers_contradiction_resolution(self):
        from research_engine.experiments.feedback_engine import FeedbackEngine
        from research_engine.experiments.experiment_spec import ExperimentResult
        engine = FeedbackEngine()
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.1)
        report = engine.process(result)
        assert any(a.action_type == "resolve_contradiction" for a in report.actions)

    def test_report_to_dict(self):
        from research_engine.experiments.feedback_engine import FeedbackEngine
        from research_engine.experiments.experiment_spec import ExperimentResult
        engine = FeedbackEngine()
        result = ExperimentResult(spec_id="s1", success=True, confidence=0.7)
        report = engine.process(result)
        d = report.to_dict()
        assert "verdict" in d
        assert "actions" in d
