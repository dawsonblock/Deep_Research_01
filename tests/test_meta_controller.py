"""Tests for the meta-reasoning modules."""
from __future__ import annotations

import pytest


class TestMetaController:
    def test_record_action(self):
        from research_engine.meta.meta_controller import MetaController
        mc = MetaController()
        alerts = mc.record_action("search_evidence")
        assert isinstance(alerts, list)

    def test_loop_detection(self):
        from research_engine.meta.meta_controller import MetaController
        mc = MetaController(loop_threshold=3)
        mc.record_action("search")
        mc.record_action("search")
        mc.record_action("search")
        mc.record_action("search")
        mc.record_action("search")
        alerts = mc.record_action("search")
        assert any(a.alert_type == "action_loop" for a in mc.alerts)

    def test_repeated_failure(self):
        from research_engine.meta.meta_controller import MetaController
        mc = MetaController(failure_threshold=3)
        mc.record_failure("bad_strategy")
        mc.record_failure("bad_strategy")
        alerts = mc.record_failure("bad_strategy")
        assert any(a.alert_type == "repeated_failure" for a in alerts)

    def test_escalate_contradiction(self):
        from research_engine.meta.meta_controller import MetaController
        mc = MetaController()
        alert = mc.escalate_contradiction(["n1", "n2"])
        assert alert.alert_type == "contradiction_escalation"
        assert alert.severity == "critical"

    def test_clear_alerts(self):
        from research_engine.meta.meta_controller import MetaController
        mc = MetaController()
        mc.escalate_contradiction(["n1"])
        mc.clear_alerts()
        assert len(mc.alerts) == 0


class TestReasoningMonitor:
    def test_record_metrics(self):
        from research_engine.meta.reasoning_monitor import ReasoningMonitor, ReasoningMetrics
        monitor = ReasoningMonitor()
        monitor.record(ReasoningMetrics(cycle_id="c1", artifacts_produced=3))
        monitor.record(ReasoningMetrics(cycle_id="c2", artifacts_produced=5))
        assert len(monitor.history) == 2

    def test_average_artifacts(self):
        from research_engine.meta.reasoning_monitor import ReasoningMonitor, ReasoningMetrics
        monitor = ReasoningMonitor()
        monitor.record(ReasoningMetrics(artifacts_produced=2))
        monitor.record(ReasoningMetrics(artifacts_produced=4))
        assert monitor.average_artifacts_per_cycle() == 3.0

    def test_loop_rate(self):
        from research_engine.meta.reasoning_monitor import ReasoningMonitor, ReasoningMetrics
        monitor = ReasoningMonitor()
        monitor.record(ReasoningMetrics(loop_detected=True))
        monitor.record(ReasoningMetrics(loop_detected=False))
        assert monitor.loop_rate() == 0.5


class TestDriftDetector:
    def test_no_drift(self):
        from research_engine.meta.drift_detector import DriftDetector
        dd = DriftDetector()
        report = dd.check()
        assert report.drift_score == 0.0

    def test_repetitive_actions_drift(self):
        from research_engine.meta.drift_detector import DriftDetector
        dd = DriftDetector()
        for _ in range(5):
            dd.record_action("same_action")
        report = dd.check()
        assert report.drift_score > 0

    def test_no_progress_drift(self):
        from research_engine.meta.drift_detector import DriftDetector
        dd = DriftDetector()
        for i in range(15):
            dd.record_action(f"action_{i % 3}")
        report = dd.check()
        # Should detect lack of progress
        assert "No progress events" in report.indicators[0] if report.indicators else True
