"""Templates for hypothesis generation."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class HypothesisTemplate:
    """Template for generating structured hypotheses."""
    name: str
    pattern: str
    description: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "pattern": self.pattern, "description": self.description}


# Default templates
TEMPLATES = [
    HypothesisTemplate(
        name="method_difference",
        pattern="The conflicting results may be due to differences in methodology",
        description="Hypothesizes methodological differences explain contradictions",
    ),
    HypothesisTemplate(
        name="dataset_bias",
        pattern="The observed effect may be an artifact of dataset selection bias",
        description="Hypothesizes dataset bias as explanation",
    ),
    HypothesisTemplate(
        name="measurement_error",
        pattern="Inconsistent results may reflect measurement or instrumentation error",
        description="Hypothesizes measurement error as explanation",
    ),
    HypothesisTemplate(
        name="scaling_effect",
        pattern="The effect may not replicate at different scales or sample sizes",
        description="Hypothesizes scale-dependent effects",
    ),
]


class TemplateRegistry:
    """Registry of hypothesis templates."""

    def __init__(self) -> None:
        self._templates: dict[str, HypothesisTemplate] = {}
        for t in TEMPLATES:
            self._templates[t.name] = t

    def get(self, name: str) -> HypothesisTemplate | None:
        return self._templates.get(name)

    def all_templates(self) -> list[HypothesisTemplate]:
        return list(self._templates.values())

    def register(self, template: HypothesisTemplate) -> None:
        self._templates[template.name] = template
