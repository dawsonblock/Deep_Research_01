"""PDF text extraction utilities."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Extracted text from a document."""
    source: str = ""
    text: str = ""
    pages: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "text": self.text,
            "page_count": len(self.pages),
            "metadata": dict(self.metadata),
        }


class PDFParser:
    """Extracts text content from PDF-like inputs."""

    def parse_text(self, raw_text: str, source: str = "") -> ParsedDocument:
        """Parse raw text content into a structured document."""
        pages = raw_text.split("\f") if "\f" in raw_text else [raw_text]
        full_text = "\n".join(p.strip() for p in pages if p.strip())
        return ParsedDocument(
            source=source,
            text=full_text,
            pages=[p.strip() for p in pages if p.strip()],
        )

    def extract_sections(self, doc: ParsedDocument) -> list[dict]:
        """Split document into sections by headings."""
        sections: list[dict] = []
        current_heading = "Introduction"
        current_lines: list[str] = []

        for line in doc.text.split("\n"):
            stripped = line.strip()
            if stripped and stripped == stripped.upper() and len(stripped.split()) <= 6:
                if current_lines:
                    sections.append({
                        "heading": current_heading,
                        "text": "\n".join(current_lines),
                    })
                current_heading = stripped
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "heading": current_heading,
                "text": "\n".join(current_lines),
            })
        return sections
