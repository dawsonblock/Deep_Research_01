"""Groups related conflicts into clusters."""
from __future__ import annotations
from collections import defaultdict

from research_engine.analysis.conflicts.conflict_detector import Conflict


class ConflictClusterer:
    """Groups related conflicts by shared claims."""

    def cluster(self, conflicts: list[Conflict]) -> list[list[Conflict]]:
        """Group conflicts that share common claim IDs."""
        if not conflicts:
            return []

        # Build adjacency from conflicts
        claim_to_conflicts: dict[str, list[int]] = defaultdict(list)
        for i, c in enumerate(conflicts):
            claim_to_conflicts[c.claim_a_id].append(i)
            claim_to_conflicts[c.claim_b_id].append(i)

        visited: set[int] = set()
        clusters: list[list[Conflict]] = []

        for i in range(len(conflicts)):
            if i in visited:
                continue
            cluster: list[Conflict] = []
            stack = [i]
            while stack:
                idx = stack.pop()
                if idx in visited:
                    continue
                visited.add(idx)
                cluster.append(conflicts[idx])
                c = conflicts[idx]
                for related_idx in claim_to_conflicts.get(c.claim_a_id, []):
                    if related_idx not in visited:
                        stack.append(related_idx)
                for related_idx in claim_to_conflicts.get(c.claim_b_id, []):
                    if related_idx not in visited:
                        stack.append(related_idx)
            clusters.append(cluster)
        return clusters
