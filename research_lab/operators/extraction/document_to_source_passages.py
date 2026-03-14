"""Document to source passages — splits a document into traceable passages."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourcePassage:
    passage_id: str
    text: str
    source_document_id: str
    start_offset: int
    end_offset: int
    section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passage_id": self.passage_id,
            "text": self.text,
            "source_document_id": self.source_document_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "section": self.section,
            "metadata": self.metadata,
        }


# Regex for splitting on paragraph boundaries (two+ newlines) or section headers
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SECTION_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Minimum passage length (characters) to keep
_MIN_PASSAGE_LENGTH = 40


def _split_into_paragraphs(text: str) -> list[tuple[str, int, int]]:
    """Split text into (paragraph_text, start_offset, end_offset) tuples."""
    paragraphs: list[tuple[str, int, int]] = []
    for match in _PARAGRAPH_SPLIT.finditer(text):
        pass  # we use split positions below

    parts = _PARAGRAPH_SPLIT.split(text)
    offset = 0
    for part in parts:
        stripped = part.strip()
        if stripped:
            start = text.find(part, offset)
            end = start + len(part)
            paragraphs.append((stripped, start, end))
            offset = end
        else:
            offset += len(part)
    return paragraphs


def _detect_section(text: str) -> str:
    """Detect if text starts with a section header."""
    match = _SECTION_HEADER.match(text)
    if match:
        return match.group(2).strip()
    return ""


class DocumentToSourcePassages:
    """Operator: split a document into source passages with offsets.

    Input: {"document_id": str, "text": str, "metadata": dict}
    Output: {"artifacts": [{"id": ..., "type": "source_passages", "data": {...}}]}
    """

    name = "document_to_source_passages"

    def __init__(self, min_passage_length: int = _MIN_PASSAGE_LENGTH) -> None:
        self.min_passage_length = min_passage_length

    def __call__(self, inputs: dict[str, Any]) -> dict[str, Any]:
        document_id = inputs.get("document_id", uuid.uuid4().hex)
        text = inputs.get("text", "")
        doc_metadata = inputs.get("metadata", {})

        if not text.strip():
            return {
                "artifacts": [{
                    "id": uuid.uuid4().hex,
                    "type": "source_passages",
                    "data": {
                        "document_id": document_id,
                        "passages": [],
                        "metadata": doc_metadata,
                    },
                }],
            }

        paragraphs = _split_into_paragraphs(text)

        current_section = ""
        passages: list[dict[str, Any]] = []

        for para_text, start, end in paragraphs:
            # Check if this paragraph is a section header
            section = _detect_section(para_text)
            if section:
                current_section = section

            if len(para_text) < self.min_passage_length:
                continue

            passage = SourcePassage(
                passage_id=uuid.uuid4().hex,
                text=para_text,
                source_document_id=document_id,
                start_offset=start,
                end_offset=end,
                section=current_section,
                metadata=doc_metadata,
            )
            passages.append(passage.to_dict())

        artifact_id = uuid.uuid4().hex
        return {
            "artifacts": [{
                "id": artifact_id,
                "type": "source_passages",
                "data": {
                    "document_id": document_id,
                    "passages": passages,
                    "passage_count": len(passages),
                    "metadata": doc_metadata,
                },
            }],
        }
