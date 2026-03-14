"""ArXiv paper discovery and metadata extraction."""
from __future__ import annotations
from dataclasses import dataclass, field
from urllib.parse import quote_plus


@dataclass
class ArxivPaper:
    """Metadata for an ArXiv paper."""
    arxiv_id: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    published: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": list(self.authors),
            "abstract": self.abstract,
            "categories": list(self.categories),
            "published": self.published,
            "url": self.url,
        }


class ArxivScraper:
    """Builds ArXiv API queries and parses results."""

    BASE_URL = "https://export.arxiv.org/api/query"

    def build_query_url(
        self,
        topic: str,
        max_results: int = 10,
        start: int = 0,
    ) -> str:
        """Build an ArXiv API query URL for a topic."""
        encoded = quote_plus(topic)
        return (
            f"{self.BASE_URL}"
            f"?search_query={encoded}"
            f"&start={start}"
            f"&max_results={max_results}"
        )

    def parse_entry(self, entry: dict) -> ArxivPaper:
        """Parse a single entry dict into an ArxivPaper."""
        return ArxivPaper(
            arxiv_id=entry.get("id", ""),
            title=entry.get("title", "").strip(),
            authors=entry.get("authors", []),
            abstract=entry.get("abstract", "").strip(),
            categories=entry.get("categories", []),
            published=entry.get("published", ""),
            url=entry.get("url", ""),
        )
