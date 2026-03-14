"""Schedules experiments for priority-aware execution."""
from __future__ import annotations
from dataclasses import dataclass, field
import bisect

from research_engine.experiments.experiment_spec import ExperimentSpec


@dataclass
class ScheduledExperiment:
    """An experiment in the scheduling queue."""
    spec: ExperimentSpec
    priority: int = 0
    status: str = "queued"

    def to_dict(self) -> dict:
        return {
            "spec_id": self.spec.spec_id,
            "priority": self.priority,
            "status": self.status,
        }


class ExperimentScheduler:
    """Queues and dispatches experiments for execution.

    Higher-priority experiments are dispatched first.
    """

    def __init__(self) -> None:
        # Sorted by priority ascending so highest priority is at the end.
        self._queue: list[ScheduledExperiment] = []
        self._running: list[ScheduledExperiment] = []
        self._completed: list[ScheduledExperiment] = []

    def submit(self, spec: ExperimentSpec, priority: int = 0) -> ScheduledExperiment:
        item = ScheduledExperiment(spec=spec, priority=priority)
        # bisect uses the item's sort order; use the priority as the key.
        keys = [e.priority for e in self._queue]
        idx = bisect.bisect_left(keys, priority)
        self._queue.insert(idx, item)
        return item

    def next(self) -> ScheduledExperiment | None:
        if not self._queue:
            return None
        item = self._queue.pop()  # highest priority is at end
        item.status = "running"
        self._running.append(item)
        return item

    def complete(self, item: ScheduledExperiment) -> None:
        item.status = "completed"
        if item in self._running:
            self._running.remove(item)
        self._completed.append(item)

    def pending_count(self) -> int:
        return len(self._queue)

    def running_count(self) -> int:
        return len(self._running)
