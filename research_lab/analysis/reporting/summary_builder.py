"""Builds human-readable summaries from reports."""
from __future__ import annotations

from research_lab.analysis.reporting.report_generator import ResearchReport


class SummaryBuilder:
    """Converts structured reports into text summaries."""

    def build(self, report: ResearchReport) -> str:
        """Build a text summary from a report."""
        lines: list[str] = []
        s = report.sections

        lines.append(f"# Research Report: {s.get('topic_summary', 'Unknown')}")
        lines.append("")

        stats = s.get("stats", {})
        lines.append(f"## Statistics")
        lines.append(f"- Claims: {stats.get('total_claims', 0)}")
        lines.append(f"- Hypotheses: {stats.get('total_hypotheses', 0)}")
        lines.append(f"- Contradictions: {stats.get('total_contradictions', 0)}")
        lines.append("")

        claims = s.get("key_claims", [])
        if claims:
            lines.append("## Key Claims")
            for c in claims[:5]:
                lines.append(f"- [{c['id']}] {c['content']}")
            lines.append("")

        contradictions = s.get("contradictions", [])
        if contradictions:
            lines.append("## Contradictions")
            for ct in contradictions:
                lines.append(f"- {ct['source']} vs {ct['target']}")
            lines.append("")

        hypotheses = s.get("open_hypotheses", [])
        if hypotheses:
            lines.append("## Open Hypotheses")
            for h in hypotheses:
                lines.append(f"- [{h['id']}] {h['content']}")

        return "\n".join(lines)
