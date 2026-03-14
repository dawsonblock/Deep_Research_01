"""Reader agent for extracting claims from papers."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ReadingResult:
    """Result of reading a paper."""
    source: str
    claims: list[dict] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "claims_count": len(self.claims),
            "passages_count": len(self.passages),
            "metadata": self.metadata,
        }


class ReaderAgent:
    """Reads papers and extracts structured claims."""

    def run(self, paper_text: str, source: str = "unknown") -> ReadingResult:
        """Extract claims from paper text."""
        from research_lab.ingestion.claim_pipeline import ClaimPipeline

        pipeline = ClaimPipeline()
        result = pipeline.run(paper_text, source=source)
        claims = result.get("data", {}).get("claims", [])
        return ReadingResult(
            source=source,
            claims=claims,
            metadata={"artifact_type": result.get("artifact_type", "")},
        )
