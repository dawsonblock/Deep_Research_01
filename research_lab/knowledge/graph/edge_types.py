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
