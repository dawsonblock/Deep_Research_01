"""Postcondition verifier — checks that operator outputs satisfy declared postconditions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""


@dataclass
class PostconditionReport:
    operator_name: str
    all_passed: bool
    checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_name": self.operator_name,
            "all_passed": self.all_passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "message": c.message}
                for c in self.checks
            ],
        }


# A postcondition function receives (inputs, outputs) and returns (passed, message).
PostconditionFn = Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]


class PostconditionVerifier:
    """Registry-based postcondition verifier.

    Operators register named postconditions.  After execution, the verifier
    runs every registered check and produces a report.
    """

    def __init__(self) -> None:
        self._postconditions: dict[str, list[tuple[str, PostconditionFn]]] = {}

    def register(
        self,
        operator_name: str,
        check_name: str,
        fn: PostconditionFn,
    ) -> None:
        self._postconditions.setdefault(operator_name, []).append((check_name, fn))

    def verify(
        self,
        operator_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> PostconditionReport:
        checks: list[CheckResult] = []
        registered = self._postconditions.get(operator_name, [])

        if not registered:
            # No postconditions registered — pass by default
            default_check = CheckResult(
                name="no_postconditions_registered",
                passed=True,
                message="No postconditions registered for this operator",
            )
            return PostconditionReport(
                operator_name=operator_name,
                all_passed=True,
                checks=[default_check],
            )

        for check_name, fn in registered:
            try:
                passed, message = fn(inputs, outputs)
            except Exception as exc:
                passed = False
                message = f"Postcondition raised exception: {exc}"
            checks.append(CheckResult(name=check_name, passed=passed, message=message))

        all_passed = all(c.passed for c in checks)
        return PostconditionReport(
            operator_name=operator_name,
            all_passed=all_passed,
            checks=checks,
        )


# ── built-in postcondition helpers ───────────────────────────────────


def output_not_empty(inputs: dict[str, Any], outputs: dict[str, Any]) -> tuple[bool, str]:
    """Check that the operator produced at least one output artifact."""
    artifacts = outputs.get("artifacts", [])
    if artifacts:
        return True, f"Produced {len(artifacts)} artifact(s)"
    return False, "No artifacts produced"


def output_matches_expected_type(expected_type: str) -> PostconditionFn:
    """Return a postcondition that checks that at least one artifact has the expected type."""

    def _check(inputs: dict[str, Any], outputs: dict[str, Any]) -> tuple[bool, str]:
        artifacts = outputs.get("artifacts", [])
        matching = [a for a in artifacts if a.get("type") == expected_type]
        if matching:
            return True, f"Found {len(matching)} artifact(s) of type {expected_type}"
        types_found = [a.get("type") for a in artifacts]
        return False, f"Expected type '{expected_type}', found: {types_found}"

    return _check
