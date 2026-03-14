"""Operator mutation logic for self-improvement."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class MutationType(Enum):
    PARAMETER_CHANGE = "parameter_change"
    PROMPT_CHANGE = "prompt_change"
    ALGORITHM_SWAP = "algorithm_swap"


@dataclass
class MutationRecord:
    """Records a mutation applied to an operator."""
    operator_name: str
    mutation_type: MutationType
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "operator_name": self.operator_name,
            "mutation_type": self.mutation_type.value,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }


class OperatorMutator:
    """Applies mutations to operator configurations."""

    def __init__(self) -> None:
        self._history: list[MutationRecord] = []

    def mutate_parameter(
        self,
        operator_name: str,
        param_name: str,
        old_value: object,
        new_value: object,
        reason: str = "",
    ) -> MutationRecord:
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.PARAMETER_CHANGE,
            before={param_name: old_value},
            after={param_name: new_value},
            reason=reason,
        )
        self._history.append(record)
        return record

    def mutate_prompt(
        self,
        operator_name: str,
        old_prompt: str,
        new_prompt: str,
        reason: str = "",
    ) -> MutationRecord:
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.PROMPT_CHANGE,
            before={"prompt": old_prompt},
            after={"prompt": new_prompt},
            reason=reason,
        )
        self._history.append(record)
        return record

    def swap_algorithm(
        self,
        operator_name: str,
        old_algorithm: str,
        new_algorithm: str,
        reason: str = "",
    ) -> MutationRecord:
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.ALGORITHM_SWAP,
            before={"algorithm": old_algorithm},
            after={"algorithm": new_algorithm},
            reason=reason,
        )
        self._history.append(record)
        return record

    @property
    def history(self) -> list[MutationRecord]:
        return list(self._history)
