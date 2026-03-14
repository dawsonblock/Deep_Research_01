"""Schedules experiments for concurrent execution."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque

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
    """Queues and dispatches experiments for execution."""

    def __init__(self) -> None:
        self._queue: deque[ScheduledExperiment] = deque()
        self._running: list[ScheduledExperiment] = []
        self._completed: list[ScheduledExperiment] = []

    def submit(self, spec: ExperimentSpec, priority: int = 0) -> ScheduledExperiment:
        item = ScheduledExperiment(spec=spec, priority=priority)
        # Insert into the queue so that higher-priority experiments are dispatched first.
        # For equal priority, preserve FIFO order.
        if not self._queue:
            self._queue.append(item)
        else:
            insert_index = None
            for idx, existing in enumerate(self._queue):
                if existing.priority < item.priority:
                    insert_index = idx
                    break
            if insert_index is None:
                # No lower-priority item found; append to preserve order among >= priority items.
                self._queue.append(item)
            else:
                self._queue.insert(insert_index, item)
        return item

    def next(self) -> ScheduledExperiment | None:
        if not self._queue:
            return None
        item = self._queue.popleft()
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
