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
