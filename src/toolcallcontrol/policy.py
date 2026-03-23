"""Map classification labels to registry profiles and optional trace requirement overrides."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyRule:
    """
    Resolved policy for a classification label.

    ``profile`` must exist on the :class:`~toolcallcontrol.tool_registry.ToolRegistry`.
    ``trace_requirements`` merges with the profile's trace requirements; rule keys win on conflict.
    """

    profile: str
    trace_requirements: dict[str, int] = field(default_factory=dict)


class ClassificationPolicyRegistry:
    """
    ``label -> PolicyRule``. Unknown labels fall back to ``default`` if provided.

    Used with a :class:`~toolcallcontrol.classifier.Classifier` at session start to set
    ``session.profile`` and merged trace quotas.
    """

    def __init__(
        self,
        rules: dict[str, PolicyRule],
        *,
        default: PolicyRule | None = None,
    ) -> None:
        self._rules = dict(rules)
        self._default = default

    def resolve(self, label: str) -> PolicyRule:
        if label in self._rules:
            return self._rules[label]
        if self._default is not None:
            return self._default
        raise KeyError(f"No policy rule for classification label {label!r} and no default")
