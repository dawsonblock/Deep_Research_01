"""State manager — central commit path for runtime transitions.

Provides transactional semantics for state changes:
    - begin transaction
    - persist transition
    - update artifact state
    - update graph state
    - commit or rollback
"""
from __future__ import annotations

from typing import Any

from research_engine.runtime.transition import Transition


class StateManager:
    """Central commit path for runtime state transitions.

    Collects transitions and commits them atomically.  The current
    implementation is in-memory; future versions will integrate with
    persistent stores.
    """

    def __init__(self) -> None:
        self._committed: list[Transition] = []
        self._pending: Transition | None = None

    def begin(self, run_id: str = "") -> Transition:
        """Begin a new transition.

        Args:
            run_id: Optional run identifier to associate with this transition.

        Returns:
            A new Transition object in 'pending' state.
        """
        self._pending = Transition(run_id=run_id)
        return self._pending

    @property
    def pending(self) -> Transition | None:
        """The currently pending transition, if any."""
        return self._pending

    def commit(self) -> Transition:
        """Commit the pending transition.

        Returns:
            The committed Transition.

        Raises:
            RuntimeError: If no transaction is pending.
        """
        if self._pending is None:
            raise RuntimeError("No pending transition to commit")
        self._pending.status = "committed"
        self._committed.append(self._pending)
        committed = self._pending
        self._pending = None
        return committed

    def rollback(self) -> Transition | None:
        """Roll back the pending transition.

        Returns:
            The rolled-back Transition, or None if nothing was pending.
        """
        if self._pending is None:
            return None
        self._pending.status = "rolled_back"
        rolled = self._pending
        self._pending = None
        return rolled

    @property
    def history(self) -> list[Transition]:
        """All committed transitions."""
        return list(self._committed)

    @property
    def committed_count(self) -> int:
        return len(self._committed)
