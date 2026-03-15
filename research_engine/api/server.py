"""Canonical API server for research_engine.

Provides REST endpoints that delegate to research_engine modules.
Backend API gradually delegates to these canonical routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_engine.api.routes import tasks, artifacts, experiments, search, runtime


@dataclass
class APIResponse:
    """Standard API response wrapper."""
    success: bool = True
    data: Any = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "data": self.data, "error": self.error}


class ResearchAPIServer:
    """Lightweight server that routes requests to canonical modules.

    In production this would be mounted as a FastAPI router; here it
    exposes the route handlers as plain methods so they can be tested
    without a running HTTP server.
    """

    def __init__(self) -> None:
        self._routes: dict[str, Any] = {}
        self._register_default_routes()

    def _register_default_routes(self) -> None:
        """Register all canonical API routes."""
        self._routes["/tasks/replan"] = tasks.replan
        self._routes["/artifacts/create"] = artifacts.create_artifact
        self._routes["/artifacts/get"] = artifacts.get_artifact
        self._routes["/artifacts/list"] = artifacts.list_artifacts
        self._routes["/experiments/run"] = experiments.run_experiment
        self._routes["/search/nodes"] = search.search_nodes
        self._routes["/runtime/runs"] = runtime.list_runs
        self._routes["/runtime/health"] = runtime.health

    def register_route(self, path: str, handler: Any) -> None:
        self._routes[path] = handler

    def handle(self, path: str, payload: dict[str, Any] | None = None) -> APIResponse:
        handler = self._routes.get(path)
        if handler is None:
            return APIResponse(success=False, error=f"Route not found: {path}")
        try:
            result = handler(payload or {})
            return APIResponse(success=True, data=result)
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    @property
    def registered_routes(self) -> list[str]:
        return sorted(self._routes.keys())
