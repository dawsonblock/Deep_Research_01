"""Side-effect processing after artifact creation."""
from __future__ import annotations
from typing import Protocol

from research_engine.core.artifacts.artifact_schema import Artifact


class SideEffect(Protocol):
    """Protocol for artifact side-effects."""
    def process(self, artifact: Artifact) -> None: ...


class SideEffectProcessor:
    """Runs registered side-effects when artifacts are created."""

    def __init__(self) -> None:
        self._effects: list[SideEffect] = []

    def register(self, effect: SideEffect) -> None:
        self._effects.append(effect)

    def process(self, artifact: Artifact) -> list[str]:
        """Run all side effects, return list of effect names that ran."""
        results: list[str] = []
        for effect in self._effects:
            effect.process(artifact)
            results.append(type(effect).__name__)
        return results
