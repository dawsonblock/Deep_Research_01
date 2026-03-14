"""Artifact schema definitions using dataclasses."""
from __future__ import annotations
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Artifact:
    """Typed artifact produced by an operator run."""
    artifact_type: str
    data: dict = field(default_factory=dict)
    artifact_id: str = ""
    producer_run: str = ""
    inputs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id:
            self.artifact_id = uuid.uuid4().hex[:16]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "producer_run": self.producer_run,
            "inputs": list(self.inputs),
            "data": dict(self.data),
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
