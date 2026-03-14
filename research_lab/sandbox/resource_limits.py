"""Resource limits for sandboxed execution."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ResourceLimits:
    """Configurable limits for sandbox execution."""
    cpu_seconds: int = 30
    memory_mb: int = 256
    network_enabled: bool = False
    max_file_size_mb: int = 10
    max_processes: int = 1

    def to_dict(self) -> dict:
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_mb": self.memory_mb,
            "network_enabled": self.network_enabled,
            "max_file_size_mb": self.max_file_size_mb,
            "max_processes": self.max_processes,
        }
