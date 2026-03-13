from __future__ import annotations

from collections.abc import Callable
from typing import Any

OperatorFn = Callable[[dict[str, Any]], dict[str, Any]]


class OperatorRegistry:
    def __init__(self) -> None:
        self._ops: dict[str, OperatorFn] = {}

    def register(self, name: str, fn: OperatorFn) -> None:
        self._ops[name] = fn

    def get(self, name: str) -> OperatorFn | None:
        return self._ops.get(name)

    def names(self) -> list[str]:
        return sorted(self._ops)


registry = OperatorRegistry()
