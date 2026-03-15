"""Meta controller — top-level meta-reasoning coordinator.

Monitors the research process for:
    - Planner loop detection
    - Repeated failed strategy detection
    - Contradiction escalation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetaAlert:
    """An alert raised by the meta-reasoning system."""
    alert_type: str = ""
    severity: str = "info"
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "metadata": self.metadata,
        }


class MetaController:
    """Monitors the research process for pathological patterns.

    Detects:
        - Repeated action loops (same action sequence cycling)
        - Strategies that keep failing
        - Unresolved contradictions that need escalation
    """

    def __init__(self, loop_threshold: int = 3, failure_threshold: int = 5) -> None:
        self._action_history: list[str] = []
        self._failure_counts: dict[str, int] = {}
        self._loop_threshold = loop_threshold
        self._failure_threshold = failure_threshold
        self._alerts: list[MetaAlert] = []

    def record_action(self, action: str) -> list[MetaAlert]:
        """Record an action and check for loops.

        Returns any new alerts generated.
        """
        self._action_history.append(action)
        alerts = self._check_loops()
        self._alerts.extend(alerts)
        return alerts

    def record_failure(self, strategy: str) -> list[MetaAlert]:
        """Record a strategy failure and check threshold.

        Returns any new alerts generated.
        """
        self._failure_counts[strategy] = self._failure_counts.get(strategy, 0) + 1
        alerts = []
        if self._failure_counts[strategy] >= self._failure_threshold:
            alert = MetaAlert(
                alert_type="repeated_failure",
                severity="warning",
                message=f"Strategy '{strategy}' has failed {self._failure_counts[strategy]} times",
                metadata={"strategy": strategy, "count": self._failure_counts[strategy]},
            )
            alerts.append(alert)
            self._alerts.append(alert)
        return alerts

    def escalate_contradiction(self, node_ids: list[str]) -> MetaAlert:
        """Escalate an unresolved contradiction."""
        alert = MetaAlert(
            alert_type="contradiction_escalation",
            severity="critical",
            message=f"Unresolved contradiction involving {len(node_ids)} nodes",
            metadata={"node_ids": node_ids},
        )
        self._alerts.append(alert)
        return alert

    def _check_loops(self) -> list[MetaAlert]:
        """Detect repeating action patterns in history."""
        alerts = []
        history = self._action_history
        if len(history) < self._loop_threshold * 2:
            return alerts
        # Check for simple repeating pattern
        recent = history[-self._loop_threshold:]
        if len(set(recent)) == 1:
            alert = MetaAlert(
                alert_type="action_loop",
                severity="warning",
                message=f"Action '{recent[0]}' repeated {self._loop_threshold} times consecutively",
                metadata={"action": recent[0], "count": self._loop_threshold},
            )
            alerts.append(alert)
        return alerts

    @property
    def alerts(self) -> list[MetaAlert]:
        return list(self._alerts)

    def clear_alerts(self) -> None:
        self._alerts.clear()
