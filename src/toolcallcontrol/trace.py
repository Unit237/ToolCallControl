"""Count tool tags on the event log and evaluate trace quotas (min reads, tests, etc.)."""

from __future__ import annotations

from collections import Counter

from .model import Decision, Event
from .tool_registry import ToolRegistry


def count_tags_from_events(events: list[Event], registry: ToolRegistry) -> Counter[str]:
    """
    Count successful tool executions by tag.

    Only **step** events with ``decision=allow``, a non-done tool call, and a known tool
    in the registry contribute; each tag on :attr:`~toolcallcontrol.model.ToolDef.tags`
    increments by one per matching event.
    """
    c: Counter[str] = Counter()
    for e in events:
        if e.kind != "step":
            continue
        if e.decision != Decision.ALLOW:
            continue
        if e.proposal.is_done():
            continue
        tid = e.proposal.tool_id
        if not tid:
            continue
        tdef = registry.get(tid)
        if not tdef:
            continue
        for tag in tdef.tags:
            c[tag] += 1
    return c


def trace_requirements_met(requirements: dict[str, int], counts: Counter[str]) -> bool:
    """Return True if every required tag meets its minimum count."""
    for tag, need in requirements.items():
        if counts.get(tag, 0) < need:
            return False
    return True


def trace_deficits(
    requirements: dict[str, int],
    counts: Counter[str],
) -> dict[str, tuple[int, int]]:
    """
    For each required tag, ``(have, need)`` when ``have < need``.

    Empty dict means all requirements satisfied.
    """
    out: dict[str, tuple[int, int]] = {}
    for tag, need in requirements.items():
        have = counts.get(tag, 0)
        if have < need:
            out[tag] = (have, need)
    return out
