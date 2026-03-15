"""Event bus — lightweight publish / subscribe for runtime observability.

Provides a central channel for recording and reacting to events such as
``task.started``, ``operator.executed``, ``artifact.created``, and
``evaluation.completed``.  Subscribers are simple callables.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    """A single runtime event.

    Attributes:
        event_type: Dot-separated event name (e.g. ``task.started``).
        payload: Arbitrary data associated with the event.
        event_id: Unique event identifier.
        timestamp: Epoch seconds when the event was created.
    """

    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:16]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
        }


class EventBus:
    """In-process event bus with topic-based subscriptions.

    Usage::

        bus = EventBus()
        bus.subscribe("task.started", my_handler)
        bus.emit("task.started", {"task_id": "t1"})
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Event], None]]] = {}
        self._history: list[Event] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(
        self, event_type: str, handler: Callable[[Event], None]
    ) -> None:
        """Register *handler* for *event_type*."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        """Create and dispatch an event, returning the :class:`Event` object."""
        event = Event(event_type=event_type, payload=payload or {})
        self._history.append(event)
        for handler in self._subscribers.get(event_type, []):
            handler(event)
        # Also dispatch to wildcard subscribers
        for handler in self._subscribers.get("*", []):
            handler(event)
        return event

    def history(self, event_type: str | None = None) -> list[Event]:
        """Return recorded events, optionally filtered by *event_type*."""
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e.event_type == event_type]

    def clear(self) -> None:
        """Reset history and remove all subscribers.

        Active subscriptions will need to be re-registered after this call.
        """
        self._subscribers.clear()
        self._history.clear()
