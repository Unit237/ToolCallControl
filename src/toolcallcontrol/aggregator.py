"""Optional consensus over N proposals before constraints (variance reduction)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

from .model import Proposal


def _proposal_key(p: Proposal) -> tuple[str | None, str]:
    args = json.dumps(p.args, sort_keys=True)
    return (p.tool_id, args)


@dataclass(frozen=True)
class NoConsensus:
    """Policy can retry, escalate, or reject."""

    proposals: tuple[Proposal, ...]
    counts: dict[tuple[str | None, str], int]


def majority_aggregate(proposals: list[Proposal]) -> Proposal | NoConsensus:
    """
    Return the mode of proposals (ties → :class:`NoConsensus`).

    Agreement is on ``(tool_id, args)`` with JSON-sorted args.
    """
    if not proposals:
        raise ValueError("proposals must be non-empty")
    if len(proposals) == 1:
        return proposals[0]

    keys = [_proposal_key(p) for p in proposals]
    counts = Counter(keys)
    (winner_key, freq), second = counts.most_common(2)[0], None
    if len(counts.most_common(2)) > 1:
        second = counts.most_common(2)[1]

    if second is not None and second[1] == freq:
        return NoConsensus(
            proposals=tuple(proposals),
            counts={k: counts[k] for k in counts},
        )

    for p in proposals:
        if _proposal_key(p) == winner_key:
            return p

    raise RuntimeError("unreachable")
