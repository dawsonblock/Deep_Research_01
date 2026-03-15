"""Operator performance metrics tracking."""
from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class OperatorMetrics:
    """Tracks performance metrics for a single operator."""
    operator_name: str
    success_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_runtime: float = 0.0
    total_runs: int = 0
    total_successes: int = 0
    failure_modes: list[dict] = field(default_factory=list)
    last_run_time: float = 0.0

    def record_run(
        self,
        success: bool,
        confidence: float = 0.0,
        runtime: float = 0.0,
        failure_reason: str | None = None,
    ) -> None:
        """Record a single operator execution result."""
        self.total_runs += 1
        if success:
            self.total_successes += 1
        self.success_rate = self.total_successes / self.total_runs

        # Running average for confidence
        prev_total_conf = self.avg_confidence * (self.total_runs - 1)
        self.avg_confidence = (prev_total_conf + confidence) / self.total_runs

        # Running average for runtime
        prev_total_rt = self.avg_runtime * (self.total_runs - 1)
        self.avg_runtime = (prev_total_rt + runtime) / self.total_runs

        self.last_run_time = time.time()

        if failure_reason:
            for fm in self.failure_modes:
                if fm["reason"] == failure_reason:
                    fm["count"] += 1
                    break
            else:
                self.failure_modes.append({"reason": failure_reason, "count": 1})

    def to_dict(self) -> dict:
        return {
            "operator_name": self.operator_name,
            "success_rate": self.success_rate,
            "avg_confidence": self.avg_confidence,
            "avg_runtime": self.avg_runtime,
            "total_runs": self.total_runs,
            "total_successes": self.total_successes,
            "failure_modes": list(self.failure_modes),
            "last_run_time": self.last_run_time,
        }


class OperatorMetricsStore:
    """Central store for all operator metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, OperatorMetrics] = {}

    def get_or_create(self, operator_name: str) -> OperatorMetrics:
        if operator_name not in self._metrics:
            self._metrics[operator_name] = OperatorMetrics(operator_name=operator_name)
        return self._metrics[operator_name]

    def record(
        self,
        operator_name: str,
        success: bool,
        confidence: float = 0.0,
        runtime: float = 0.0,
        failure_reason: str | None = None,
    ) -> OperatorMetrics:
        m = self.get_or_create(operator_name)
        m.record_run(success, confidence, runtime, failure_reason)
        return m

    def get_metrics(self, operator_name: str) -> OperatorMetrics | None:
        return self._metrics.get(operator_name)

    def all_metrics(self) -> dict[str, OperatorMetrics]:
        return dict(self._metrics)

    def underperforming(self, threshold: float = 0.6) -> list[OperatorMetrics]:
        return [m for m in self._metrics.values() if m.total_runs > 0 and m.success_rate < threshold]
