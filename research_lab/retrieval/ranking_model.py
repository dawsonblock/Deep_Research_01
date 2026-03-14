"""Evidence ranking model."""
from __future__ import annotations


class RankingModel:
    """Ranks evidence by combined quality scores."""

    def __init__(
        self,
        retrieval_weight: float = 0.4,
        source_quality_weight: float = 0.3,
        claim_match_weight: float = 0.2,
        replication_weight: float = 0.1,
    ) -> None:
        self.retrieval_weight = retrieval_weight
        self.source_quality_weight = source_quality_weight
        self.claim_match_weight = claim_match_weight
        self.replication_weight = replication_weight

    def score(
        self,
        retrieval_score: float = 0.0,
        source_quality: float = 0.0,
        claim_match: float = 0.0,
        replication_factor: float = 0.0,
    ) -> float:
        """Compute combined evidence score."""
        return (
            self.retrieval_weight * retrieval_score
            + self.source_quality_weight * source_quality
            + self.claim_match_weight * claim_match
            + self.replication_weight * replication_factor
        )

    def rank(self, items: list[dict]) -> list[dict]:
        """Rank items by combined score."""
        for item in items:
            item["combined_score"] = self.score(
                retrieval_score=item.get("retrieval_score", 0),
                source_quality=item.get("source_quality", 0),
                claim_match=item.get("claim_match", 0),
                replication_factor=item.get("replication_factor", 0),
            )
        return sorted(items, key=lambda x: x.get("combined_score", 0), reverse=True)
