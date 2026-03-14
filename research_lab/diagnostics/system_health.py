"""System health monitoring."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class HealthCheck:
    """Result of a system health check."""
    component: str
    status: str = "healthy"
    details: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "status": self.status,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class SystemHealth:
    """Monitors system component health."""

    def __init__(self) -> None:
        self._checks: list[HealthCheck] = []

    def check_component(self, component: str, is_healthy: bool, details: str = "") -> HealthCheck:
        status = "healthy" if is_healthy else "degraded"
        check = HealthCheck(component=component, status=status, details=details)
        self._checks.append(check)
        return check

    def is_healthy(self) -> bool:
        if not self._checks:
            return True
        recent = self._latest_per_component()
        return all(c.status == "healthy" for c in recent.values())

    def _latest_per_component(self) -> dict[str, HealthCheck]:
        latest: dict[str, HealthCheck] = {}
        for check in self._checks:
            if check.component not in latest or check.timestamp > latest[check.component].timestamp:
                latest[check.component] = check
        return latest

    def summary(self) -> dict:
        latest = self._latest_per_component()
        return {
            "healthy": self.is_healthy(),
            "components": {k: v.to_dict() for k, v in latest.items()},
        }
