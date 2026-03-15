"""Scheduler — manages execution queue with priority and dependencies.

First version with:
    - priority queue
    - dependency resolution
    - retries
    - safe parallel slots
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class ScheduledItem:
    """An item in the scheduler's priority queue.

    Lower priority number = higher priority (runs first).
    """
    priority: int
    item_id: str = field(compare=False)
    operator_name: str = field(compare=False, default="")
    dependencies: list[str] = field(compare=False, default_factory=list)
    retries: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    metadata: dict[str, Any] = field(compare=False, default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "item_id": self.item_id,
            "operator_name": self.operator_name,
            "dependencies": self.dependencies,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }


class Scheduler:
    """Priority-based execution scheduler with dependency resolution.

    Items are scheduled with a priority (lower = runs first) and optional
    dependencies.  An item is only ready when all its dependencies have
    been marked as completed.
    """

    def __init__(self, max_parallel: int = 1) -> None:
        self._queue: list[ScheduledItem] = []
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self.max_parallel = max_parallel

    def submit(self, item: ScheduledItem) -> None:
        """Submit an item to the scheduler."""
        heapq.heappush(self._queue, item)

    def next_ready(self) -> ScheduledItem | None:
        """Return the highest-priority item whose dependencies are met.

        Does not remove the item from the queue — call `mark_completed`
        or `mark_failed` after execution.
        """
        for item in sorted(self._queue):
            deps_met = all(d in self._completed for d in item.dependencies)
            if deps_met and item.item_id not in self._completed and item.item_id not in self._failed:
                return item
        return None

    def mark_completed(self, item_id: str) -> None:
        """Mark an item as successfully completed."""
        self._completed.add(item_id)
        self._queue = [i for i in self._queue if i.item_id != item_id]
        heapq.heapify(self._queue)

    def mark_failed(self, item_id: str, retry: bool = True) -> bool:
        """Mark an item as failed. Returns True if retried, False if exhausted."""
        for item in self._queue:
            if item.item_id == item_id:
                if retry and item.retries < item.max_retries:
                    item.retries += 1
                    return True
                else:
                    self._failed.add(item_id)
                    self._queue = [i for i in self._queue if i.item_id != item_id]
                    heapq.heapify(self._queue)
                    return False
        return False

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def failed_count(self) -> int:
        return len(self._failed)
