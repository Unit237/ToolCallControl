"""Proposer: stateless LLM interface. Returns one or N proposals. This example uses a mock."""

from .model import Proposal


def propose(
    prompt: str,
    context: list[dict],
    tool_ids: list[str],
    n: int = 1,
) -> list[Proposal]:
    """
    Mock proposer. In production this would call an LLM with the prompt and tool schemas.
    For demo we return a deterministic sequence based on step count (context length).
    """
    step = len(context)

    # Simulate a short loop: propose add, then search, then done
    if step == 0:
        return [Proposal(tool_id="add", args={"a": 2, "b": 3})] * n
    if step == 1:
        return [Proposal(tool_id="search", args={"query": "control plane"})] * n
    if step >= 2:
        return [Proposal(tool_id=None, args={})] * n  # done

    return [Proposal(tool_id=None, args={})] * n
