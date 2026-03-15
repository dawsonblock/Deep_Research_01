"""Task API routes — delegates to planner and executor."""
from __future__ import annotations

from typing import Any

from research_engine.planner.agenda_manager import AgendaManager
from research_engine.planner.research_planner import PlannerState


_agenda_manager = AgendaManager()


def replan(payload: dict[str, Any]) -> dict[str, Any]:
    """Replan based on current state.

    Expects payload with optional state fields:
        open_hypotheses, unresolved_conflicts, untested_claims,
        evidence_gaps, pending_experiments.
    """
    state = PlannerState(
        open_hypotheses=payload.get("open_hypotheses", 0),
        unresolved_conflicts=payload.get("unresolved_conflicts", 0),
        untested_claims=payload.get("untested_claims", 0),
        evidence_gaps=payload.get("evidence_gaps", 0),
        pending_experiments=payload.get("pending_experiments", 0),
    )
    proposal = _agenda_manager.plan(state)
    if proposal is None:
        return {"actions": [], "rationale": "No proposals generated"}
    return proposal.to_dict()
