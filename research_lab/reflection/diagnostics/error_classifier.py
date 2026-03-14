"""Classifies errors in reasoning and experiments."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    LOGICAL = "logical_error"
    DATA = "data_error"
    METHOD = "method_error"
    CONFIDENCE = "confidence_error"
    RUNTIME = "runtime_error"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedError:
    """An error with a classification."""
    error_id: str = ""
    category: ErrorCategory = ErrorCategory.UNKNOWN
    description: str = ""
    source: str = ""
    severity: float = 0.5

    def to_dict(self) -> dict:
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "description": self.description,
            "source": self.source,
            "severity": self.severity,
        }


class ErrorClassifier:
    """Classifies errors based on context and error messages."""

    PATTERNS: dict[str, ErrorCategory] = {
        "confidence": ErrorCategory.CONFIDENCE,
        "assertion": ErrorCategory.LOGICAL,
        "data": ErrorCategory.DATA,
        "timeout": ErrorCategory.RUNTIME,
        "method": ErrorCategory.METHOD,
        "invalid": ErrorCategory.DATA,
    }

    def classify(self, error_msg: str, source: str = "", error_id: str = "") -> ClassifiedError:
        """Classify an error message into a category."""
        lower = error_msg.lower()
        category = ErrorCategory.UNKNOWN
        for keyword, cat in self.PATTERNS.items():
            if keyword in lower:
                category = cat
                break
        return ClassifiedError(
            error_id=error_id,
            category=category,
            description=error_msg,
            source=source,
        )
