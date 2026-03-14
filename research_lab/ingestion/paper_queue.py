"""Queue for managing paper ingestion tasks."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
import time


@dataclass
class PaperTask:
    """A paper queued for ingestion."""
    paper_id: str
    source: str = ""
    priority: int = 0
    status: str = "queued"
    queued_at: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.queued_at == 0.0:
            self.queued_at = time.time()

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "source": self.source,
            "priority": self.priority,
            "status": self.status,
            "queued_at": self.queued_at,
        }


class PaperQueue:
    """FIFO queue for paper ingestion with priority support."""

    def __init__(self) -> None:
        self._queue: deque[PaperTask] = deque()
        self._processed: list[PaperTask] = []

    def enqueue(self, task: PaperTask) -> None:
        self._queue.append(task)

    def dequeue(self) -> PaperTask | None:
        if not self._queue:
            return None
        task = self._queue.popleft()
        task.status = "processing"
        return task

    def mark_done(self, task: PaperTask) -> None:
        task.status = "done"
        self._processed.append(task)

    def pending_count(self) -> int:
        return len(self._queue)

    def processed_count(self) -> int:
        return len(self._processed)

    def all_pending(self) -> list[PaperTask]:
        return list(self._queue)
