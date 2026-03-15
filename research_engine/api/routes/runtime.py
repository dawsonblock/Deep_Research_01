"""Runtime API routes — run registry, scheduler, health."""
from __future__ import annotations

from typing import Any

from research_engine.core.runtime.run_registry import RunRegistry


_registry = RunRegistry()


def list_runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """List runs, optionally filtered by operator_name."""
    operator_name = payload.get("operator_name")
    runs = _registry.list_runs(operator_name=operator_name)
    return [r.to_dict() for r in runs]


def health(payload: dict[str, Any]) -> dict[str, Any]:
    """Health check for the runtime."""
    return {
        "status": "ok",
        "total_runs": len(_registry.list_runs()),
    }
