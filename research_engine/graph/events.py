"""Graph events — defines graph transition events.

Events are emitted when the graph state changes and can be consumed
by the state manager, belief updater, or other downstream systems.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphEvent:
    """A single graph state transition event."""
    event_id: str = ""
    event_type: str = ""
    node_id: str = ""
    edge_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "node_id": self.node_id,
            "edge_id": self.edge_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventLog:
    """Collects graph events for a transaction or execution cycle."""

    def __init__(self) -> None:
        self._events: list[GraphEvent] = []

    def emit(self, event_type: str, **kwargs: Any) -> GraphEvent:
        event = GraphEvent(event_type=event_type, **kwargs)
        self._events.append(event)
        return event

    def node_added(self, node_id: str, **kwargs: Any) -> GraphEvent:
        return self.emit("node_added", node_id=node_id, **kwargs)

    def node_updated(self, node_id: str, **kwargs: Any) -> GraphEvent:
        return self.emit("node_updated", node_id=node_id, **kwargs)

    def node_removed(self, node_id: str, **kwargs: Any) -> GraphEvent:
        return self.emit("node_removed", node_id=node_id, **kwargs)

    def edge_added(self, edge_id: str, **kwargs: Any) -> GraphEvent:
        return self.emit("edge_added", edge_id=edge_id, **kwargs)

    def edge_removed(self, edge_id: str, **kwargs: Any) -> GraphEvent:
        return self.emit("edge_removed", edge_id=edge_id, **kwargs)

    @property
    def events(self) -> list[GraphEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
