#!/usr/bin/env python3
"""
End-to-end ToolCallControl example you can run and extend.

  # Offline (no API keys): mock classifier + mock proposer
  python examples/full_agent_example.py

  # Live: classification + agent both call OpenAI (needs OPENAI_API_KEY)
  USE_OPENAI=1 python examples/full_agent_example.py

Requires (live): pip install 'toolcallcontrol[openai]'
Run from repo root: pip install -e .
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

# Repo root on path when run as `python examples/full_agent_example.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from toolcallcontrol import (
    ClassificationPolicyRegistry,
    ConstraintPipeline,
    EventLog,
    LoopRunner,
    MockClassifier,
    MockProposer,
    OpenAIClassifier,
    PolicyRule,
    ProfileConfig,
    Proposal,
    ToolRegistry,
)


# ---------------------------------------------------------------------------
# OpenAI tool schemas — must match tool_id + args your executor understands
# (see toolcallcontrol.builtin_tools.execute_server_tool)
# ---------------------------------------------------------------------------

def openai_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "add",
                "description": "Add two numbers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search a corpus.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "corpus": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_terminal",
                "description": "Run a shell command (client venue in real apps).",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        },
    ]


def message_to_proposal(message: Any) -> Proposal:
    """
    Map one OpenAI chat.completions message → Proposal.

    - If there are tool_calls → first call becomes Proposal(tool_id, args).
    - If there are no tool_calls → model is done → Proposal(None, {}).
    """
    tcs = getattr(message, "tool_calls", None) or []
    if not tcs:
        return Proposal(None, {})

    tc = tcs[0]
    name = tc.function.name
    raw = tc.function.arguments or "{}"
    try:
        args = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    return Proposal(name, args)


def build_transcript(prompt: str, context: list[dict[str, Any]]) -> str:
    """Turn loop context into one user-visible string for the next LLM call."""
    parts = [prompt]
    for row in context:
        if row.get("trace_feedback"):
            parts.append(
                "\n[System: cannot finish yet — trace requirements not met]\n"
                + json.dumps(row["trace_feedback"], indent=2)
            )
        prop = row.get("proposal")
        out = row.get("outcome")
        if prop is not None and hasattr(prop, "tool_id"):
            parts.append(f"\n[Step result] tool={prop.tool_id!r} args={prop.args!r} outcome={out!r}")
    return "\n".join(parts)


class OpenAIChatProposer:
    """
    Real agent: one chat completion per step, maps tool_calls → Proposal.

    This is the integration point that was missing as a named helper in the library.
    """

    def __init__(self, *, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI()
        self._model = model
        self._tools = openai_tool_definitions()

    def propose(
        self,
        prompt: str,
        context: list[dict[str, Any]],
        tool_ids: list[str],
        *,
        n: int = 1,
        session: Any = None,
    ) -> list[Proposal]:
        _ = tool_ids
        _ = session
        user_content = build_transcript(prompt, context)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding agent. Use tools when helpful. "
                    "When the task is complete, respond without calling tools."
                ),
            },
            {"role": "user", "content": user_content},
        ]
        proposals: list[Proposal] = []
        for _ in range(n):
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message
            proposals.append(message_to_proposal(msg))
        return proposals


def main() -> None:
    use_openai = os.environ.get("USE_OPENAI", "").lower() in ("1", "true", "yes")

    registry = ToolRegistry(
        profiles={
            "bug_profile": ProfileConfig(
                name="bug_profile",
                tools=["add", "search", "run_terminal"],
                max_steps=15,
                proposal_n=1,
                trace_requirements={"read": 1},
                labels={"workflow": "bug"},
            ),
            "write_profile": ProfileConfig(
                name="write_profile",
                tools=["search", "run_terminal"],
                max_steps=12,
                trace_requirements={"shell": 1},
                labels={"workflow": "write"},
            ),
        }
    )

    policy = ClassificationPolicyRegistry(
        rules={
            "bug": PolicyRule(profile="bug_profile"),
            "write": PolicyRule(profile="write_profile"),
        },
        default=PolicyRule(profile="write_profile"),
    )

    if use_openai:
        classifier: Any = OpenAIClassifier(
            model=os.environ.get("CLASSIFIER_MODEL", "gpt-4o-mini"),
            labels=["bug", "write"],
        )
        proposer: Any = OpenAIChatProposer(model=os.environ.get("AGENT_MODEL", "gpt-4o-mini"))
    else:
        classifier = MockClassifier("bug")
        proposer = MockProposer()

    log = EventLog()
    runner = LoopRunner(
        log,
        registry,
        ConstraintPipeline(registry),
        proposer=proposer,
        classifier=classifier,
        policy_registry=policy,
    )

    session = runner.create_session(
        "Find why login fails after the last deploy.",
        profile="write_profile",
        max_steps=20,
    )
    result = runner.run(session)

    print("=== Session ===")
    print("profile:", session.profile)
    print("classification:", session.classification)
    print("effective_trace_requirements:", session.effective_trace_requirements)
    print()
    print("=== Event log (JSON) ===")
    print(json.dumps(result["log"], indent=2))


if __name__ == "__main__":
    main()
