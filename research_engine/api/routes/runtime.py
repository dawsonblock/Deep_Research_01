"""Runtime API routes — run registry, scheduler, health."""
from __future__ import annotations

from typing import Any

from research_engine.core.runtime.run_registry import RunRegistry


_registry: RunRegistry | None = None


def set_run_registry(registry: RunRegistry) -> None:
    """Configure the runtime API to use a shared RunRegistry instance.

    This allows the API layer and execution layer (e.g., CanonicalExecutor /
    VerifiedExecutor) to share a single registry, so that /runtime/runs reflects
    all runs registered elsewhere.
    """
    global _registry
    _registry = registry


def get_run_registry() -> RunRegistry:
    """Return the RunRegistry used by the runtime API.

    If no registry has been injected yet, a default in-memory RunRegistry is
    created. This preserves the previous behavior while still allowing the
    application to inject a shared instance via set_run_registry().
    """
    global _registry
    if _registry is None:
        _registry = RunRegistry()
    return _registry


def list_runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """List runs, optionally filtered by operator_name."""
    operator_name = payload.get("operator_name")
    runs = get_run_registry().list_runs(operator_name=operator_name)
    return [r.to_dict() for r in runs]


def health(payload: dict[str, Any]) -> dict[str, Any]:
    """Health check for the runtime."""
    return {
        "status": "ok",
        "total_runs": len(get_run_registry().list_runs()),
    }
