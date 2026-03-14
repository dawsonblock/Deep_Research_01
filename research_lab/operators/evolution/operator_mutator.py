"""Operator mutation logic for self-improvement."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class MutationType(Enum):
    PARAMETER_CHANGE = "parameter_change"
    PROMPT_CHANGE = "prompt_change"
    ALGORITHM_SWAP = "algorithm_swap"
    THRESHOLD_TUNING = "threshold_tuning"
    TEMPLATE_SELECTION = "template_selection"
    RANKING_WEIGHT = "ranking_weight"


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

    def tune_threshold(
        self,
        operator_name: str,
        threshold_name: str,
        old_value: float,
        new_value: float,
        reason: str = "",
    ) -> MutationRecord:
        """Mutate a threshold parameter within bounded range."""
        clamped = max(0.0, min(1.0, new_value))
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.THRESHOLD_TUNING,
            before={threshold_name: old_value},
            after={threshold_name: clamped},
            reason=reason,
        )
        self._history.append(record)
        return record

    def select_template(
        self,
        operator_name: str,
        old_template: str,
        new_template: str,
        reason: str = "",
    ) -> MutationRecord:
        """Switch the prompt template used by an operator."""
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.TEMPLATE_SELECTION,
            before={"template": old_template},
            after={"template": new_template},
            reason=reason,
        )
        self._history.append(record)
        return record

    def adjust_ranking_weight(
        self,
        operator_name: str,
        weight_name: str,
        old_weight: float,
        new_weight: float,
        reason: str = "",
    ) -> MutationRecord:
        """Adjust a ranking weight, clamped to [0.0, 1.0]."""
        clamped = max(0.0, min(1.0, new_weight))
        record = MutationRecord(
            operator_name=operator_name,
            mutation_type=MutationType.RANKING_WEIGHT,
            before={weight_name: old_weight},
            after={weight_name: clamped},
            reason=reason,
        )
        self._history.append(record)
        return record
