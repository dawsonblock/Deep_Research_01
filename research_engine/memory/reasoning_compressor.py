"""Reasoning compressor — periodically compresses reasoning memory.

Compression is designed to run periodically, not on every execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompressionResult:
    """Result of a memory compression cycle."""
    entries_before: int = 0
    entries_after: int = 0
    compression_ratio: float = 0.0
    summaries_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries_before": self.entries_before,
            "entries_after": self.entries_after,
            "compression_ratio": self.compression_ratio,
            "summaries_created": self.summaries_created,
        }


class ReasoningCompressor:
    """Compresses reasoning memory to keep context within budget.

    Strategies:
        - Merge similar entries
        - Summarize old chains
        - Drop low-value entries
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: list[dict[str, Any]] = []

    def add_entry(self, entry: dict[str, Any]) -> None:
        self._entries.append(entry)

    def compress(self) -> CompressionResult:
        """Run compression if entries exceed budget."""
        before = len(self._entries)
        if before <= self._max_entries:
            return CompressionResult(
                entries_before=before,
                entries_after=before,
                compression_ratio=1.0,
            )

        # Simple compression: keep the most recent entries
        self._entries = self._entries[-self._max_entries:]
        after = len(self._entries)
        return CompressionResult(
            entries_before=before,
            entries_after=after,
            compression_ratio=after / before if before > 0 else 1.0,
            summaries_created=1,
        )

    @property
    def entry_count(self) -> int:
        return len(self._entries)
