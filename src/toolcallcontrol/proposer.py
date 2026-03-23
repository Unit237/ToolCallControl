"""Proposer protocol: LLM proposes; you implement with your model client."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .model import Proposal, Session


@runtime_checkable
class Proposer(Protocol):
    """
    Stateless proposal source (typically wrapping an LLM API).

    Implementations should accept optional ``session`` so they can read
    :attr:`~toolcallcontrol.model.Session.classification` and
    :attr:`~toolcallcontrol.model.Session.effective_trace_requirements`
    set by the control plane — **without** re-running classification or keyword heuristics.
    """

    def propose(
        self,
        prompt: str,
        context: list[dict],
        tool_ids: list[str],
        *,
        n: int = 1,
        session: Session | None = None,
    ) -> list[Proposal]:
        """Return ``n`` proposals (same prompt; use for consensus / K-of-N)."""
        ...


class MockProposer:
    """
    Deterministic mock for tests and demos.

    Simulates: ``add`` → ``search`` → done.
    """

    def propose(
        self,
        prompt: str,
        context: list[dict],
        tool_ids: list[str],
        *,
        n: int = 1,
        session: Session | None = None,
    ) -> list[Proposal]:
        step = len(context)
        if step == 0:
            base = Proposal(tool_id="add", args={"a": 2, "b": 3})
        elif step == 1:
            base = Proposal(tool_id="search", args={"query": "control plane"})
        else:
            base = Proposal(tool_id=None, args={})

        return [base] * n


def propose(
    prompt: str,
    context: list[dict],
    tool_ids: list[str],
    *,
    n: int = 1,
    proposer: Proposer | None = None,
    session: Session | None = None,
) -> list[Proposal]:
    """Convenience: call a :class:`MockProposer` if none passed."""
    p = proposer or MockProposer()
    return p.propose(prompt, context, tool_ids, n=n, session=session)
