"""Security policy for sandbox execution."""
from __future__ import annotations


class SecurityPolicy:
    """Defines what operations are allowed in the sandbox."""

    DEFAULT_BLOCKED = [
        "import os",
        "import subprocess",
        "import shutil",
        "__import__",
        "eval(",
        "exec(",
        "open(",
        "import socket",
    ]

    def __init__(self, blocked_patterns: list[str] | None = None) -> None:
        self.blocked_patterns = blocked_patterns or list(self.DEFAULT_BLOCKED)

    def is_allowed(self, code: str) -> bool:
        """Check if code passes security policy."""
        for pattern in self.blocked_patterns:
            if pattern in code:
                return False
        return True

    def add_blocked_pattern(self, pattern: str) -> None:
        if pattern not in self.blocked_patterns:
            self.blocked_patterns.append(pattern)
