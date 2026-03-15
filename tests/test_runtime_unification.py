"""Tests for the runtime-unification modules.

Covers:
    - Task model (Phase 3)
    - EventBus observability (Phase 9)
    - ExperimentEvaluator (Phase 4)
    - Replanner (Phase 7)
    - Plan simulator / generator / selector
    - RuntimeController (Phase 1)
"""
from __future__ import annotations


# ---------------------------------------------------------------
# Phase 3 — Task model
# ---------------------------------------------------------------

class TestTask:

    def test_task_creation_defaults(self):
        from research_engine.core.tasks.task import Task
        t = Task(description="extract claims")
        assert t.task_id  # auto-generated
        assert t.status == "pending"
        assert t.created_at > 0

    def test_task_lifecycle(self):
        from research_engine.core.tasks.task import Task, TaskStatus
        t = Task(description="summarize")
        assert t.is_ready
        t.mark_running()
        assert t.status == TaskStatus.RUNNING
        assert not t.is_ready
        t.mark_completed()
        assert t.status == TaskStatus.COMPLETED

    def test_task_failed(self):
        from research_engine.core.tasks.task import Task, TaskStatus
        t = Task()
        t.mark_running()
        t.mark_failed()
        assert t.status == TaskStatus.FAILED

    def test_task_replanned(self):
        from research_engine.core.tasks.task import Task, TaskStatus
        t = Task()
        t.mark_replanned()
        assert t.status == TaskStatus.REPLANNED

    def test_task_dependencies_block_readiness(self):
        from research_engine.core.tasks.task import Task
        t = Task(dependencies=["other_task"])
        assert not t.is_ready

    def test_task_to_dict(self):
        from research_engine.core.tasks.task import Task
        t = Task(description="test", operator="op", priority=3)
        d = t.to_dict()
        assert d["description"] == "test"
        assert d["operator"] == "op"
        assert d["priority"] == 3
        assert "task_id" in d

    def test_task_custom_id(self):
        from research_engine.core.tasks.task import Task
        t = Task(task_id="custom123")
        assert t.task_id == "custom123"


# ---------------------------------------------------------------
# Phase 9 — EventBus
# ---------------------------------------------------------------

class TestEventBus:

    def test_emit_and_history(self):
        from research_engine.core.events.event_bus import EventBus
        bus = EventBus()
        event = bus.emit("task.started", {"task_id": "t1"})
        assert event.event_type == "task.started"
        assert len(bus.history()) == 1
        assert bus.history("task.started")[0].payload["task_id"] == "t1"

    def test_subscriber_called(self):
        from research_engine.core.events.event_bus import EventBus
        received = []
        bus = EventBus()
        bus.subscribe("op.done", lambda e: received.append(e))
        bus.emit("op.done", {"result": "ok"})
        assert len(received) == 1
        assert received[0].payload["result"] == "ok"

    def test_wildcard_subscriber(self):
        from research_engine.core.events.event_bus import EventBus
        received = []
        bus = EventBus()
        bus.subscribe("*", lambda e: received.append(e))
        bus.emit("a.b")
        bus.emit("c.d")
        assert len(received) == 2

    def test_filtered_history(self):
        from research_engine.core.events.event_bus import EventBus
        bus = EventBus()
        bus.emit("task.started")
        bus.emit("task.completed")
        bus.emit("task.started")
        assert len(bus.history("task.started")) == 2
        assert len(bus.history("task.completed")) == 1

    def test_clear(self):
        from research_engine.core.events.event_bus import EventBus
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        bus.emit("x")
        bus.clear()
        assert len(bus.history()) == 0

    def test_event_to_dict(self):
        from research_engine.core.events.event_bus import Event
        e = Event(event_type="test", payload={"k": "v"})
        d = e.to_dict()
        assert d["event_type"] == "test"
        assert d["payload"]["k"] == "v"
        assert "event_id" in d


# ---------------------------------------------------------------
# Phase 4 — ExperimentEvaluator
# ---------------------------------------------------------------

class TestExperimentEvaluator:

    def test_no_artifacts(self):
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        result = ev.evaluate({"task_id": "t1"}, [])
        assert result.score == 0.0
        assert result.metrics["completion"] == 0.0

    def test_single_artifact(self):
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        artifacts = [{"artifact_type": "summary", "confidence": 0.8}]
        result = ev.evaluate({"task_id": "t2"}, artifacts)
        assert result.score > 0
        assert result.metrics["completion"] == 1.0

    def test_multiple_artifacts_same_type(self):
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        artifacts = [
            {"artifact_type": "claim", "confidence": 0.9},
            {"artifact_type": "claim", "confidence": 0.7},
        ]
        result = ev.evaluate({"task_id": "t3"}, artifacts)
        assert result.metrics["consistency"] == 1.0  # same type

    def test_multiple_artifacts_different_types(self):
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        artifacts = [
            {"artifact_type": "claim"},
            {"artifact_type": "summary"},
        ]
        result = ev.evaluate({"task_id": "t4"}, artifacts)
        assert result.metrics["consistency"] == 0.5  # 2 types

    def test_custom_metric(self):
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        ev.register_metric("always_one", lambda t, a: 1.0)
        result = ev.evaluate({"task_id": "t5"}, [{"artifact_type": "x"}])
        assert "always_one" in result.metrics
        assert result.metrics["always_one"] == 1.0

    def test_evaluation_to_dict(self):
        from research_engine.analysis.experiment_evaluator import EvaluationResult
        er = EvaluationResult(task_id="t", score=0.7, metrics={"m": 0.5})
        d = er.to_dict()
        assert d["task_id"] == "t"
        assert d["score"] == 0.7


# ---------------------------------------------------------------
# Phase 7 — Replanner
# ---------------------------------------------------------------

class TestReplanner:

    def test_high_score_no_replan(self):
        from research_engine.planner.replanner import Replanner
        from research_engine.core.tasks.task import Task
        rp = Replanner()
        t = Task(description="test")
        decision = rp.replan(t, score=0.8)
        assert not decision.retry
        assert len(decision.new_tasks) == 0

    def test_low_score_retry(self):
        from research_engine.planner.replanner import Replanner
        from research_engine.core.tasks.task import Task
        rp = Replanner(retry_threshold=0.3)
        decision = rp.replan(Task(), score=0.1)
        assert decision.retry

    def test_medium_score_expand(self):
        from research_engine.planner.replanner import Replanner
        from research_engine.core.tasks.task import Task
        rp = Replanner(retry_threshold=0.3, expand_threshold=0.6)
        decision = rp.replan(Task(description="research"), score=0.4)
        assert not decision.retry
        assert len(decision.new_tasks) == 1
        assert decision.new_tasks[0].operator == "collect_sources"

    def test_replan_decision_to_dict(self):
        from research_engine.planner.replanner import ReplanDecision
        rd = ReplanDecision(reason="ok")
        d = rd.to_dict()
        assert d["reason"] == "ok"
        assert d["retry"] is False


# ---------------------------------------------------------------
# Plan Simulator
# ---------------------------------------------------------------

class TestPlanSimulator:

    def test_simulate_scores_plan(self):
        from research_engine.planner.simulator import PlanSimulator, Plan, Step
        sim = PlanSimulator()
        plan = Plan(steps=[Step(operator="collect_sources")])
        scored = sim.simulate(plan)
        assert scored.score is not None
        assert scored.score > 0

    def test_simulate_graph_aware_penalty(self):
        from research_engine.planner.simulator import PlanSimulator, Plan, Step
        sim = PlanSimulator(graph_topics={"AI safety"})
        plan = Plan(steps=[Step(operator="collect_sources", inputs={"topic": "AI safety"})])
        scored = sim.simulate(plan)
        # With graph penalty, score should be halved vs. without
        sim2 = PlanSimulator()
        plan2 = Plan(steps=[Step(operator="collect_sources", inputs={"topic": "AI safety"})])
        scored2 = sim2.simulate(plan2)
        assert scored.score < scored2.score

    def test_unknown_operator_gets_default_value(self):
        from research_engine.planner.simulator import PlanSimulator, Plan, Step
        sim = PlanSimulator()
        plan = Plan(steps=[Step(operator="unknown_op")])
        scored = sim.simulate(plan)
        assert scored.score == 0.1  # default

    def test_multi_step_plan(self):
        from research_engine.planner.simulator import PlanSimulator, Plan, Step
        sim = PlanSimulator()
        plan = Plan(steps=[
            Step(operator="collect_sources"),
            Step(operator="extract_claims"),
            Step(operator="summarize"),
        ])
        scored = sim.simulate(plan)
        assert scored.score == 0.4 + 0.3 + 0.1


class TestPlanGenerator:

    def test_generate_returns_plans(self):
        from research_engine.planner.simulator import PlanGenerator
        gen = PlanGenerator()
        plans = gen.generate("study AI safety")
        assert len(plans) >= 1
        assert all(len(p.steps) > 0 for p in plans)

    def test_generate_respects_max(self):
        from research_engine.planner.simulator import PlanGenerator
        gen = PlanGenerator()
        plans = gen.generate("topic", max_plans=2)
        assert len(plans) <= 2

    def test_generate_custom_operators(self):
        from research_engine.planner.simulator import PlanGenerator
        gen = PlanGenerator()
        plans = gen.generate("topic", operators=["a", "b"])
        operators_used = {s.operator for p in plans for s in p.steps}
        assert operators_used <= {"a", "b"}


class TestPlanSelector:

    def test_select_highest(self):
        from research_engine.planner.simulator import PlanSelector, Plan, Step
        sel = PlanSelector()
        p1 = Plan(steps=[Step(operator="a")], score=0.3)
        p2 = Plan(steps=[Step(operator="b")], score=0.9)
        best = sel.select([p1, p2])
        assert best is p2

    def test_select_empty(self):
        from research_engine.planner.simulator import PlanSelector
        assert PlanSelector().select([]) is None

    def test_select_ignores_unscored(self):
        from research_engine.planner.simulator import PlanSelector, Plan, Step
        sel = PlanSelector()
        p1 = Plan(steps=[Step(operator="a")], score=None)
        p2 = Plan(steps=[Step(operator="b")], score=0.5)
        best = sel.select([p1, p2])
        assert best is p2


# ---------------------------------------------------------------
# Phase 1 — RuntimeController
# ---------------------------------------------------------------

class TestRuntimeController:

    @staticmethod
    def _make_executor(artifacts=None):
        """Return a simple executor that produces *artifacts*."""
        default = [{"artifact_type": "summary", "confidence": 0.8}]
        result = default if artifacts is None else artifacts
        def executor(task_dict):
            return result
        return executor

    def test_run_task_success(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        ctrl = RuntimeController(executor=self._make_executor())
        result = ctrl.run_task(Task(description="test"))
        assert result.success
        assert len(result.artifacts) == 1
        assert result.evaluation is not None
        assert result.evaluation.score > 0

    def test_run_task_emits_events(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        ctrl = RuntimeController(executor=self._make_executor())
        ctrl.run_task(Task(description="test"))
        types = [e.event_type for e in ctrl.event_bus.history()]
        assert "task.started" in types
        assert "operator.executed" in types
        assert "evaluation.completed" in types
        assert "task.completed" in types

    def test_run_task_executor_error(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task, TaskStatus
        def bad_executor(td):
            raise RuntimeError("boom")
        ctrl = RuntimeController(executor=bad_executor)
        result = ctrl.run_task(Task(description="fail"))
        assert not result.success
        assert "boom" in result.errors[0]
        assert result.task.status == TaskStatus.FAILED

    def test_run_task_graph_updater_called(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        calls = []
        def updater(task_dict, artifacts, eval_dict):
            calls.append((task_dict, artifacts, eval_dict))
        ctrl = RuntimeController(
            executor=self._make_executor(),
            graph_updater=updater,
        )
        ctrl.run_task(Task(description="g"))
        assert len(calls) == 1

    def test_run_task_replan_on_low_score(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        ctrl = RuntimeController(executor=self._make_executor(artifacts=[]))
        result = ctrl.run_task(Task(description="empty"))
        # No artifacts → score 0 → retry
        assert result.replan is not None
        assert result.replan.retry

    def test_noop_executor(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        ctrl = RuntimeController()  # no executor → noop
        result = ctrl.run_task(Task(description="noop"))
        assert result.success  # completes, just produces 0 artifacts

    def test_runtime_result_to_dict(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        ctrl = RuntimeController(executor=self._make_executor())
        result = ctrl.run_task(Task(description="dict"))
        d = result.to_dict()
        assert "task" in d
        assert "artifacts" in d
        assert "evaluation" in d
        assert "success" in d

    def test_custom_evaluator(self):
        from research_engine.core.runtime.runtime_controller import RuntimeController
        from research_engine.core.tasks.task import Task
        from research_engine.analysis.experiment_evaluator import ExperimentEvaluator
        ev = ExperimentEvaluator()
        ev.register_metric("bonus", lambda t, a: 1.0)
        ctrl = RuntimeController(executor=self._make_executor(), evaluator=ev)
        result = ctrl.run_task(Task(description="custom eval"))
        assert "bonus" in result.evaluation.metrics
