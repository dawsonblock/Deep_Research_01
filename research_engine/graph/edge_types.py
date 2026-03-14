"""Edge type definitions for the belief graph."""

from __future__ import annotations

from enum import Enum


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    TESTS = "tests"
    PRODUCED = "produced"
    SUMMARIZES = "summarizes"
    CONTRIBUTES_TO = "contributes_to"
    INVESTIGATES = "investigates"
    EXPLORES = "explores"
    SUPERSEDES = "supersedes"
    REVISES = "revises"
    INVALIDATED_BY = "invalidated_by"
    STRENGTHENED_BY = "strengthened_by"
    WEAKENED_BY = "weakened_by"
    OBSERVED_AT = "observed_at"
