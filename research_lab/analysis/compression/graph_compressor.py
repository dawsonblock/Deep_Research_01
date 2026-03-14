"""Compresses knowledge graphs by clustering related nodes."""
from __future__ import annotations
from collections import defaultdict

from research_lab.knowledge.graph.graph_store import GraphStore, GraphNode
from research_lab.knowledge.graph.node_types import NodeType


class GraphCompressor:
    """Compresses a knowledge graph by clustering related claims."""

    def cluster_by_type(self, store: GraphStore) -> dict[str, list[GraphNode]]:
        """Group nodes by their type."""
        clusters: dict[str, list[GraphNode]] = defaultdict(list)
        for node in store.query_nodes():
            clusters[node.node_type.value].append(node)
        return dict(clusters)

    def compress(self, store: GraphStore, max_per_cluster: int = 10) -> dict:
        """Compress graph into summary clusters."""
        clusters = self.cluster_by_type(store)
        summary: dict[str, list[dict]] = {}
        for type_name, nodes in clusters.items():
            sorted_nodes = sorted(
                nodes,
                key=lambda n: n.metadata.get("confidence", 0),
                reverse=True,
            )
            summary[type_name] = [
                {"id": n.node_id, "content": n.content[:200]}
                for n in sorted_nodes[:max_per_cluster]
            ]
        return {
            "cluster_count": len(summary),
            "clusters": summary,
            "total_nodes": sum(len(v) for v in clusters.values()),
        }
