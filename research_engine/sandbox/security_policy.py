"""Security policy for sandbox execution.

NOTE: This is a **non-security stub**. The substring-based check is trivially
bypassed (e.g. ``from os import system``, dynamic attribute access, etc.).
Production sandbox isolation MUST use AST-based analysis or a proper
sandboxing library such as RestrictedPython.
"""
from __future__ import annotations


class SecurityPolicy:
    """Defines what operations are allowed in the sandbox.

    .. warning::
       Current implementation uses simple substring matching and does NOT
       provide real security isolation.  See module docstring for details.
    """

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
