"""Artifact type definitions for the research engine."""
from __future__ import annotations
from enum import Enum


class ArtifactType(Enum):
    CLAIM_CANDIDATE_SET = "claim_candidate_set"
    NORMALIZED_CLAIM_SET = "normalized_claim_set"
    EVIDENCE_LINK_SET = "evidence_link_set"
    EXPERIMENT_RESULT = "experiment_result"
    HYPOTHESIS = "hypothesis"
    RESEARCH_SUMMARY = "research_summary"
    CONFLICT_REPORT = "conflict_report"
    SOURCE_PASSAGES = "source_passages"
    REASONING_CHAIN = "reasoning_chain"
    TOPIC_SUMMARY = "topic_summary"
