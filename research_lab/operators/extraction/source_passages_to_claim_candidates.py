"""Source passages to claim candidates — extracts candidate claims from passages."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClaimCandidate:
    candidate_id: str
    text: str
    source_passage_id: str
    source_offset: int = 0
    claim_type: str = "assertion"
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "text": self.text,
            "source_passage_id": self.source_passage_id,
            "source_offset": self.source_offset,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


# Heuristic patterns for claim-bearing sentences
_CLAIM_INDICATORS = [
    re.compile(r"\b(show(?:s|ed|n)?|demonstrat(?:e[sd]?|ing)|prov(?:e[sd]?|ing))\b", re.IGNORECASE),
    re.compile(r"\b(suggest(?:s|ed)?|indicat(?:e[sd]?|ing)|impl(?:y|ies|ied))\b", re.IGNORECASE),
    re.compile(r"\b(find(?:s|ing)?|found|observ(?:e[sd]?|ing)|report(?:s|ed)?)\b", re.IGNORECASE),
    re.compile(r"\b(increas(?:e[sd]?|ing)|decreas(?:e[sd]?|ing)|correlat(?:e[sd]?|ing))\b", re.IGNORECASE),
    re.compile(r"\b(significant(?:ly)?|caus(?:e[sd]?|ing|al)|effect(?:s|ive)?)\b", re.IGNORECASE),
    re.compile(r"\b(conclude[sd]?|concluding|establish(?:e[sd]?|ing))\b", re.IGNORECASE),
    re.compile(r"\b(confirm(?:s|ed)?|support(?:s|ed)?|contradict(?:s|ed)?)\b", re.IGNORECASE),
]

# Split into sentences
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _score_sentence(sentence: str) -> float:
    """Score how likely a sentence contains a claim (0.0-1.0)."""
    score = 0.0
    for pattern in _CLAIM_INDICATORS:
        if pattern.search(sentence):
            score += 0.15
    return min(score, 1.0)


def _classify_claim_type(sentence: str) -> str:
    """Classify the type of claim in a sentence."""
    lower = sentence.lower()
    if any(w in lower for w in ("cause", "causal", "because", "leads to", "results in")):
        return "causal"
    if any(w in lower for w in ("correlat", "associat", "linked to", "related to")):
        return "correlational"
    if any(w in lower for w in ("compare", "versus", "better than", "worse than", "outperform")):
        return "comparative"
    if any(w in lower for w in ("define", "definition", "is a", "refers to", "known as")):
        return "definitional"
    return "assertion"


class SourcePassagesToClaimCandidates:
    """Operator: extract claim candidates from source passages.

    Input: {"passages": list[dict]}  (as produced by document_to_source_passages)
    Output: {"artifacts": [{"id": ..., "type": "claim_candidate_set", "data": {...}}]}
    """

    name = "source_passages_to_claim_candidates"

    def __init__(self, min_score: float = 0.15) -> None:
        self.min_score = min_score

    def __call__(self, inputs: dict[str, Any]) -> dict[str, Any]:
        passages = inputs.get("passages", [])
        document_id = inputs.get("document_id", "")

        candidates: list[dict[str, Any]] = []

        for passage in passages:
            passage_id = passage.get("passage_id", uuid.uuid4().hex)
            passage_text = passage.get("text", "")
            passage_offset = passage.get("start_offset", 0)

            sentences = _SENTENCE_SPLIT.split(passage_text)

            sentence_offset = 0
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    sentence_offset += len(sentence) + 1
                    continue

                score = _score_sentence(sentence)
                if score >= self.min_score:
                    claim_type = _classify_claim_type(sentence)
                    candidate = ClaimCandidate(
                        candidate_id=uuid.uuid4().hex,
                        text=sentence,
                        source_passage_id=passage_id,
                        source_offset=passage_offset + sentence_offset,
                        claim_type=claim_type,
                        confidence=round(score, 3),
                        metadata={"document_id": document_id},
                    )
                    candidates.append(candidate.to_dict())

                sentence_offset += len(sentence) + 1

        artifact_id = uuid.uuid4().hex
        return {
            "artifacts": [{
                "id": artifact_id,
                "type": "claim_candidate_set",
                "data": {
                    "candidates": candidates,
                    "candidate_count": len(candidates),
                    "document_id": document_id,
                },
            }],
        }
