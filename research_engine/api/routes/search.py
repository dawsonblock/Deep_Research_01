"""Search API routes — delegates to retrieval layer."""
from __future__ import annotations

from typing import Any

from research_engine.graph.graph_store import GraphStore
from research_engine.graph.node_types import NodeType


_graph_store = GraphStore()


def search_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Search graph nodes by type and content filter."""
    node_type_str = payload.get("node_type")
    node_type = None
    if node_type_str:
        try:
            node_type = NodeType(node_type_str)
        except ValueError:
            pass
    content_filter = payload.get("content_filter")
    nodes = _graph_store.query_nodes(node_type=node_type, content_filter=content_filter)
    return [n.to_dict() for n in nodes]
