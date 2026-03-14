"""Normalize claims — deduplicates and normalizes claim candidates into canonical form."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedClaim:
    claim_id: str
    text: str
    original_text: str
    claim_type: str
    confidence: float
    provenance: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "original_text": self.original_text,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "metadata": self.metadata,
        }


def _normalize_text(text: str) -> str:
    """Normalize claim text: lowercase, collapse whitespace, strip punctuation edges."""
    text = text.strip()
    # Collapse internal whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove trailing punctuation for comparison
    text = text.rstrip(".")
    return text


def _texts_are_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Simple token-overlap similarity check for deduplication."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return False
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union)
    return jaccard >= threshold


class NormalizeClaims:
    """Operator: normalize and deduplicate claim candidates.

    Input: {"candidates": list[dict]}  (as produced by source_passages_to_claim_candidates)
    Output: {"artifacts": [{"id": ..., "type": "normalized_claim_set", "data": {...}}]}
    """

    name = "normalize_claims"

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        self.similarity_threshold = similarity_threshold

    def __call__(self, inputs: dict[str, Any]) -> dict[str, Any]:
        candidates = inputs.get("candidates", [])
        document_id = inputs.get("document_id", "")

        normalized: list[NormalizedClaim] = []
        seen_texts: list[str] = []

        for candidate in candidates:
            original_text = candidate.get("text", "")
            norm_text = _normalize_text(original_text)

            if not norm_text:
                continue

            # Deduplication check
            is_duplicate = False
            for existing in seen_texts:
                if _texts_are_similar(norm_text, existing, self.similarity_threshold):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            seen_texts.append(norm_text)

            claim = NormalizedClaim(
                claim_id=uuid.uuid4().hex,
                text=norm_text,
                original_text=original_text,
                claim_type=candidate.get("claim_type", "assertion"),
                confidence=candidate.get("confidence", 0.5),
                provenance={
                    "source_passage_id": candidate.get("source_passage_id", ""),
                    "source_offset": candidate.get("source_offset", 0),
                    "candidate_id": candidate.get("candidate_id", ""),
                    "document_id": document_id,
                },
                metadata=candidate.get("metadata", {}),
            )
            normalized.append(claim)

        artifact_id = uuid.uuid4().hex
        return {
            "artifacts": [{
                "id": artifact_id,
                "type": "normalized_claim_set",
                "data": {
                    "claims": [c.to_dict() for c in normalized],
                    "claim_count": len(normalized),
                    "document_id": document_id,
                    "deduplicated_count": len(candidates) - len(normalized),
                },
            }],
        }
