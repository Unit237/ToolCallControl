import json

import pytest

from toolcallcontrol import ClassificationError, OpenAIClassifier


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def test_openai_classifier_parses_json() -> None:
    payload = json.dumps({"label": "bug", "confidence": 0.91, "reasoning": "has stack trace"})
    c = OpenAIClassifier(
        model="gpt-4o-mini",
        labels=["bug", "write"],
        client=_FakeClient(payload),
    )
    r = c.classify("the app crashes on login")
    assert r.label == "bug"
    assert abs(r.confidence - 0.91) < 1e-6
    assert r.metadata.get("reasoning")


def test_openai_classifier_rejects_bad_label() -> None:
    payload = json.dumps({"label": "unknown", "confidence": 1.0})
    c = OpenAIClassifier(
        model="x",
        labels=["bug", "write"],
        client=_FakeClient(payload),
    )
    with pytest.raises(ClassificationError, match="not in allowed"):
        c.classify("hi")
