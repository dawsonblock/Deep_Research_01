"""End-to-end claim ingestion pipeline."""
from __future__ import annotations

from research_lab.ingestion.pdf_parser import PDFParser, ParsedDocument
from research_lab.operators.extraction.document_to_source_passages import (
    DocumentToSourcePassages,
)
from research_lab.operators.extraction.source_passages_to_claim_candidates import (
    SourcePassagesToClaimCandidates,
)
from research_lab.operators.extraction.normalize_claims import NormalizeClaims


class ClaimPipeline:
    """Orchestrates: document → passages → candidates → normalized claims."""

    def __init__(self) -> None:
        self.parser = PDFParser()
        self.passage_op = DocumentToSourcePassages()
        self.candidate_op = SourcePassagesToClaimCandidates()
        self.normalize_op = NormalizeClaims()

    def run(self, raw_text: str, source: str = "unknown") -> dict:
        """Run the full claim extraction pipeline.
        
        Returns the final normalized_claim_set artifact dict.
        """
        # Step 1: Parse document
        doc = self.parser.parse_text(raw_text, source=source)

        # Step 2: Extract passages
        passage_input = {"document_text": doc.text, "source_id": source}
        passage_result = self.passage_op(passage_input)

        # Step 3: Extract claim candidates
        candidate_result = self.candidate_op(passage_result)

        # Step 4: Normalize claims
        normalized_result = self.normalize_op(candidate_result)

        return normalized_result
