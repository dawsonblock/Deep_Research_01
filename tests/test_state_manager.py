"""Tests for the state manager, transition, and scheduler modules."""
from __future__ import annotations

import pytest


class TestTransition:
    def test_create_transition(self):
        from research_engine.runtime.transition import Transition
        t = Transition(run_id="r1")
        assert t.transition_id
        assert t.run_id == "r1"
        assert t.status == "pending"

    def test_add_task_change(self):
        from research_engine.runtime.transition import Transition
        t = Transition()
        t.add_task_change("t1", {"status": "running"})
        assert len(t.task_changes) == 1
        assert t.task_changes[0]["task_id"] == "t1"

    def test_add_artifact(self):
        from research_engine.runtime.transition import Transition
        t = Transition()
        t.add_artifact("a1", {"type": "claim"})
        assert len(t.artifact_changes) == 1

    def test_add_graph_event(self):
        from research_engine.runtime.transition import Transition
        t = Transition()
        t.add_graph_event({"type": "node_added", "node_id": "n1"})
        assert len(t.graph_events) == 1

    def test_add_belief_update(self):
        from research_engine.runtime.transition import Transition
        t = Transition()
        t.add_belief_update({"claim_id": "c1", "confidence": 0.8})
        assert len(t.belief_updates) == 1

    def test_to_dict(self):
        from research_engine.runtime.transition import Transition
        t = Transition(run_id="r1")
        d = t.to_dict()
        assert d["run_id"] == "r1"
        assert "transition_id" in d


class TestStateManager:
    def test_begin_transaction(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        t = sm.begin("r1")
        assert t.run_id == "r1"
        assert sm.pending is not None

    def test_commit(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        sm.begin("r1")
        committed = sm.commit()
        assert committed.status == "committed"
        assert sm.pending is None
        assert sm.committed_count == 1

    def test_rollback(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        sm.begin("r1")
        rolled = sm.rollback()
        assert rolled.status == "rolled_back"
        assert sm.pending is None
        assert sm.committed_count == 0

    def test_commit_without_begin_raises(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        with pytest.raises(RuntimeError):
            sm.commit()

    def test_rollback_without_begin_returns_none(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        assert sm.rollback() is None

    def test_history(self):
        from research_engine.runtime.state_manager import StateManager
        sm = StateManager()
        sm.begin("r1")
        sm.commit()
        sm.begin("r2")
        sm.commit()
        assert len(sm.history) == 2


class TestScheduler:
    def test_submit_and_next(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=1, item_id="a", operator_name="op1"))
        item = s.next_ready()
        assert item is not None
        assert item.item_id == "a"

    def test_priority_order(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=5, item_id="low"))
        s.submit(ScheduledItem(priority=1, item_id="high"))
        item = s.next_ready()
        assert item.item_id == "high"

    def test_dependency_resolution(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=1, item_id="a"))
        s.submit(ScheduledItem(priority=1, item_id="b", dependencies=["a"]))
        # b should not be ready until a completes
        item = s.next_ready()
        assert item.item_id == "a"
        s.mark_completed("a")
        item = s.next_ready()
        assert item.item_id == "b"

    def test_mark_completed(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=1, item_id="a"))
        s.mark_completed("a")
        assert s.completed_count == 1
        assert s.pending_count == 0

    def test_mark_failed_retry(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=1, item_id="a", max_retries=2))
        retried = s.mark_failed("a")
        assert retried is True
        assert s.pending_count == 1

    def test_mark_failed_exhausted(self):
        from research_engine.runtime.scheduler import Scheduler, ScheduledItem
        s = Scheduler()
        s.submit(ScheduledItem(priority=1, item_id="a", max_retries=0))
        retried = s.mark_failed("a")
        assert retried is False
        assert s.failed_count == 1
