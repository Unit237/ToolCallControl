"""OpenAI-compatible LLM classification (optional ``openai`` package)."""

from __future__ import annotations

import json
from typing import Any

from .exceptions import ClassificationError
from .model import ClassificationResult


def _require_openai() -> Any:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "OpenAIClassifier requires the 'openai' package. "
            "Install with: pip install 'toolcallcontrol[openai]'"
        ) from e
    return OpenAI


def _build_system_prompt(labels: list[str], extra: str | None) -> str:
    lines = [
        "You classify the user's task into exactly one label.",
        "Respond with a single JSON object only, no markdown.",
        'Schema: {"label": <string>, "confidence": <number 0..1>, "reasoning": <optional string>}.',
        f"Allowed labels (choose exactly one): {json.dumps(labels)}",
    ]
    if extra and extra.strip():
        lines.append(extra.strip())
    return "\n".join(lines)


class OpenAIClassifier:
    """
    First-class classifier using an OpenAI-compatible chat completion.

    Pass ``model`` and the allowed ``labels``; the model returns JSON with ``label`` and
    optional ``confidence``. Use with :class:`~toolcallcontrol.policy.ClassificationPolicyRegistry`
    so each label maps to a :class:`~toolcallcontrol.policy.PolicyRule`.

    Install: ``pip install 'toolcallcontrol[openai]'``

    For non-OpenAI providers, pass ``client`` with a compatible ``chat.completions.create``.
    """

    def __init__(
        self,
        *,
        model: str,
        labels: list[str],
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt_extra: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        if not labels:
            raise ValueError("labels must be non-empty")
        self._model = model
        self._labels = list(labels)
        self._system = _build_system_prompt(self._labels, system_prompt_extra)
        self._temperature = temperature
        if client is not None:
            self._client = client
        else:
            OpenAI = _require_openai()
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            if base_url is not None:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)

    def classify(self, request: str, *, context: list[dict] | None = None) -> ClassificationResult:
        _ = context
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": request},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        if not raw or not str(raw).strip():
            raise ClassificationError("Classification model returned empty content")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ClassificationError(f"Classification JSON parse failed: {e}") from e
        label = str(data.get("label", "")).strip()
        if label not in self._labels:
            raise ClassificationError(
                f"Model returned label {label!r} not in allowed {self._labels!r}"
            )
        conf = data.get("confidence", 1.0)
        try:
            confidence = float(conf)
        except (TypeError, ValueError) as e:
            raise ClassificationError(f"Invalid confidence: {conf!r}") from e
        meta: dict[str, Any] = {}
        if isinstance(data.get("reasoning"), str):
            meta["reasoning"] = data["reasoning"]
        return ClassificationResult(label=label, confidence=confidence, metadata=meta)
