"""Node type definitions for the belief graph."""

from __future__ import annotations

from enum import Enum


class NodeType(str, Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    RESULT = "result"
    FINDING = "finding"
    THEORY = "theory"
    RESEARCH_FRONTIER = "research_frontier"
    BELIEF_STATE = "belief_state"
    FINDING_VERSION = "finding_version"
    THEORY_VERSION = "theory_version"
    EVIDENCE_SNAPSHOT = "evidence_snapshot"
    EXPERIMENT_REVISION = "experiment_revision"
