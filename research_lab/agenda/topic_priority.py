"""Topic priority ranking based on uncertainty and impact."""
from __future__ import annotations

from research_lab.agenda.topic_manager import ResearchTopic


class TopicPrioritizer:
    """Ranks research topics by combined uncertainty and priority score."""

    def __init__(self, uncertainty_weight: float = 0.6, priority_weight: float = 0.4) -> None:
        self.uncertainty_weight = uncertainty_weight
        self.priority_weight = priority_weight

    def score(self, topic: ResearchTopic) -> float:
        return (
            self.uncertainty_weight * topic.uncertainty
            + self.priority_weight * topic.priority
        )

    def rank(self, topics: list[ResearchTopic]) -> list[ResearchTopic]:
        return sorted(topics, key=lambda t: self.score(t), reverse=True)

    def top_n(self, topics: list[ResearchTopic], n: int = 5) -> list[ResearchTopic]:
        return self.rank(topics)[:n]
