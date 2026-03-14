"""Tests for the claim extraction pipeline (end-to-end and per-operator)."""

from __future__ import annotations

import json
import os
import pytest

from research_lab.operators.extraction.document_to_source_passages import (
    DocumentToSourcePassages,
)
from research_lab.operators.extraction.source_passages_to_claim_candidates import (
    SourcePassagesToClaimCandidates,
)
from research_lab.operators.extraction.normalize_claims import NormalizeClaims
from research_lab.core.runtime.artifact_validator import ArtifactValidator
from research_lab.core.runtime.verified_executor import VerifiedExecutor
from research_lab.core.runtime.run_registry import RunStatus


SAMPLE_PAPER = """
# Introduction

This study investigates the relationship between sleep duration and cognitive performance
in adults aged 25 to 65. Previous research has shown that sleep deprivation significantly
impairs working memory and executive function. Our findings suggest that individuals
sleeping fewer than six hours per night demonstrate measurably reduced reaction times.

# Methods

We conducted a randomized controlled trial with 200 participants over twelve weeks.
Participants were assigned to one of four sleep duration groups: less than six hours,
six to seven hours, seven to eight hours, and more than eight hours. Cognitive performance
was measured using standardized tests administered weekly.

# Results

The results indicate a significant correlation between sleep duration and cognitive
test scores. Participants in the seven to eight hour group showed the highest average
scores, while those sleeping fewer than six hours scored significantly lower. We found
that each additional hour of sleep increased test performance by approximately 12 percent.

The data also shows that chronic sleep restriction leads to cumulative cognitive deficits.
These findings confirm earlier studies by Smith et al. that established a dose-response
relationship between sleep and cognition.

# Discussion

Our observations support the hypothesis that adequate sleep is essential for maintaining
cognitive function. The results contradict the common belief that individuals can adapt
to reduced sleep without performance costs. We conclude that seven to eight hours remains
the optimal sleep duration for cognitive health.
"""


class TestDocumentToSourcePassages:
    def test_splits_into_passages(self) -> None:
        op = DocumentToSourcePassages()
        result = op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        artifacts = result["artifacts"]
        assert len(artifacts) == 1
        data = artifacts[0]["data"]
        assert data["document_id"] == "doc-1"
        assert len(data["passages"]) >= 3  # at least intro, methods, results

    def test_preserves_offsets(self) -> None:
        op = DocumentToSourcePassages()
        result = op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        passages = result["artifacts"][0]["data"]["passages"]
        for p in passages:
            assert "start_offset" in p
            assert "end_offset" in p
            assert p["start_offset"] < p["end_offset"]
            assert p["passage_id"]

    def test_empty_document(self) -> None:
        op = DocumentToSourcePassages()
        result = op({"document_id": "doc-empty", "text": ""})
        passages = result["artifacts"][0]["data"]["passages"]
        assert len(passages) == 0

    def test_detects_sections(self) -> None:
        op = DocumentToSourcePassages()
        result = op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        passages = result["artifacts"][0]["data"]["passages"]
        sections = {p.get("section") for p in passages}
        # Should detect at least some sections
        assert len(sections) >= 1


class TestSourcePassagesToClaimCandidates:
    def test_extracts_candidates(self) -> None:
        passages_op = DocumentToSourcePassages()
        passages_result = passages_op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        passages = passages_result["artifacts"][0]["data"]["passages"]

        claims_op = SourcePassagesToClaimCandidates()
        result = claims_op({"passages": passages, "document_id": "doc-1"})
        artifacts = result["artifacts"]
        assert len(artifacts) == 1
        candidates = artifacts[0]["data"]["candidates"]
        assert len(candidates) > 0

    def test_candidates_have_source_references(self) -> None:
        passages_op = DocumentToSourcePassages()
        passages_result = passages_op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        passages = passages_result["artifacts"][0]["data"]["passages"]

        claims_op = SourcePassagesToClaimCandidates()
        result = claims_op({"passages": passages, "document_id": "doc-1"})
        candidates = result["artifacts"][0]["data"]["candidates"]
        for c in candidates:
            assert c["source_passage_id"]
            assert "source_offset" in c

    def test_candidates_are_typed(self) -> None:
        passages_op = DocumentToSourcePassages()
        passages_result = passages_op({"document_id": "doc-1", "text": SAMPLE_PAPER})
        passages = passages_result["artifacts"][0]["data"]["passages"]

        claims_op = SourcePassagesToClaimCandidates()
        result = claims_op({"passages": passages, "document_id": "doc-1"})
        candidates = result["artifacts"][0]["data"]["candidates"]
        valid_types = {"assertion", "causal", "correlational", "comparative", "definitional"}
        for c in candidates:
            assert c["claim_type"] in valid_types


class TestNormalizeClaims:
    def test_normalizes_candidates(self) -> None:
        candidates = [
            {
                "candidate_id": "c1",
                "text": "Sleep deprivation significantly impairs working memory.",
                "source_passage_id": "p1",
                "source_offset": 0,
                "claim_type": "assertion",
                "confidence": 0.6,
            },
            {
                "candidate_id": "c2",
                "text": "Results indicate a significant correlation.",
                "source_passage_id": "p2",
                "source_offset": 100,
                "claim_type": "correlational",
                "confidence": 0.45,
            },
        ]
        op = NormalizeClaims()
        result = op({"candidates": candidates, "document_id": "doc-1"})
        claims = result["artifacts"][0]["data"]["claims"]
        assert len(claims) == 2
        for c in claims:
            assert c["text"]
            assert c["confidence"] > 0
            assert c["provenance"]["source_passage_id"]

    def test_deduplicates_similar(self) -> None:
        candidates = [
            {
                "candidate_id": "c1",
                "text": "Sleep deprivation impairs working memory significantly.",
                "source_passage_id": "p1",
                "source_offset": 0,
                "claim_type": "assertion",
                "confidence": 0.6,
            },
            {
                "candidate_id": "c2",
                "text": "Sleep deprivation significantly impairs working memory.",
                "source_passage_id": "p2",
                "source_offset": 50,
                "claim_type": "assertion",
                "confidence": 0.5,
            },
        ]
        op = NormalizeClaims()
        result = op({"candidates": candidates, "document_id": "doc-1"})
        claims = result["artifacts"][0]["data"]["claims"]
        assert len(claims) == 1  # duplicates removed

    def test_empty_candidates(self) -> None:
        op = NormalizeClaims()
        result = op({"candidates": [], "document_id": "doc-1"})
        claims = result["artifacts"][0]["data"]["claims"]
        assert len(claims) == 0


class TestClaimPipelineEndToEnd:
    """End-to-end: document → passages → claim candidates → normalized claims."""

    def test_full_pipeline(self) -> None:
        # Step 1: Document to passages
        doc_op = DocumentToSourcePassages()
        passages_result = doc_op({"document_id": "paper-1", "text": SAMPLE_PAPER})
        passages_data = passages_result["artifacts"][0]["data"]
        assert passages_data["passage_count"] > 0

        # Step 2: Passages to claim candidates
        claims_op = SourcePassagesToClaimCandidates()
        claims_result = claims_op({
            "passages": passages_data["passages"],
            "document_id": "paper-1",
        })
        candidates_data = claims_result["artifacts"][0]["data"]
        assert candidates_data["candidate_count"] > 0

        # Step 3: Normalize claims
        norm_op = NormalizeClaims()
        norm_result = norm_op({
            "candidates": candidates_data["candidates"],
            "document_id": "paper-1",
        })
        norm_data = norm_result["artifacts"][0]["data"]
        assert norm_data["claim_count"] > 0
        assert norm_data["document_id"] == "paper-1"

        # Verify all claims have provenance
        for claim in norm_data["claims"]:
            assert claim["provenance"]["document_id"] == "paper-1"
            assert claim["provenance"]["source_passage_id"]

    def test_full_pipeline_validated(self) -> None:
        """Run the full pipeline through the verified executor."""
        # Step 1: Document to passages (not a validated type, passes)
        executor = VerifiedExecutor()
        doc_op = DocumentToSourcePassages()
        r1 = executor.execute(doc_op, {"document_id": "paper-1", "text": SAMPLE_PAPER})
        assert r1.status == RunStatus.VERIFIED_SUCCESS

        # Step 2: Passages to claim candidates
        passages = r1.artifact_manifest  # we need the actual data from operator
        passages_result = doc_op({"document_id": "paper-1", "text": SAMPLE_PAPER})
        passages_data = passages_result["artifacts"][0]["data"]

        claims_op = SourcePassagesToClaimCandidates()
        r2 = executor.execute(
            claims_op,
            {"passages": passages_data["passages"], "document_id": "paper-1"},
        )
        assert r2.status == RunStatus.VERIFIED_SUCCESS

        # Step 3: Normalize claims
        claims_result = claims_op({
            "passages": passages_data["passages"],
            "document_id": "paper-1",
        })
        candidates_data = claims_result["artifacts"][0]["data"]

        norm_op = NormalizeClaims()
        r3 = executor.execute(
            norm_op,
            {"candidates": candidates_data["candidates"], "document_id": "paper-1"},
        )
        assert r3.status == RunStatus.VERIFIED_SUCCESS

    def test_artifact_validation_on_claim_candidate_set(self) -> None:
        validator = ArtifactValidator()
        good_data = {
            "candidates": [{
                "text": "X causes Y",
                "source_passage_id": "p1",
            }],
        }
        result = validator.validate("a1", "claim_candidate_set", good_data)
        assert result.valid

        bad_data = {"candidates": []}
        result = validator.validate("a2", "claim_candidate_set", bad_data)
        assert not result.valid

    def test_artifact_validation_on_normalized_claim_set(self) -> None:
        validator = ArtifactValidator()
        good_data = {
            "claims": [{
                "text": "X causes Y",
                "confidence": 0.8,
                "provenance": {"source_passage_id": "p1"},
            }],
        }
        result = validator.validate("a1", "normalized_claim_set", good_data)
        assert result.valid

        bad_data = {
            "claims": [{"text": "X causes Y"}],  # missing confidence + provenance
        }
        result = validator.validate("a2", "normalized_claim_set", bad_data)
        assert not result.valid

    def test_schema_file_exists(self) -> None:
        """Verify schema JSON files exist and are valid JSON."""
        schema_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "research_lab",
            "schemas",
        )
        for name in ["claim_candidate_set.json", "normalized_claim_set.json"]:
            path = os.path.join(schema_dir, name)
            assert os.path.exists(path), f"Schema file missing: {name}"
            with open(path) as f:
                schema = json.load(f)
            assert "$schema" in schema
            assert "properties" in schema
