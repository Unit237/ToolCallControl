"""Prompt / task classification: feeds profile + trace policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .model import ClassificationResult


@runtime_checkable
class Classifier(Protocol):
    """Maps a user request to a classification label (LLM, rules, or hybrid)."""

    def classify(self, request: str, *, context: list[dict] | None = None) -> ClassificationResult:
        ...


class CallableClassifier:
    """
    Wrap any function ``(request) -> ClassificationResult``.

    Use this for **LLM classification**: implement the callable with your chat completion
    (JSON schema, tool call, or parsing), not keyword matching on the prompt.
    """

    def __init__(self, fn: Callable[[str], ClassificationResult]) -> None:
        self._fn = fn

    def classify(self, request: str, *, context: list[dict] | None = None) -> ClassificationResult:
        return self._fn(request)


class MockClassifier:
    """Fixed label for tests and demos."""

    def __init__(self, label: str = "default", *, confidence: float = 1.0) -> None:
        self.label = label
        self.confidence = confidence

    def classify(self, request: str, *, context: list[dict] | None = None) -> ClassificationResult:
        return ClassificationResult(label=self.label, confidence=self.confidence, metadata={})
