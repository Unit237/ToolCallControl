"""Core types: proposals, tools, events, sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


class Venue(str, Enum):
    """Where a tool runs after the control plane approves it."""

    SERVER = "server"
    CLIENT = "client"


class Decision(str, Enum):
    """Policy decision for a proposal."""

    ALLOW = "allow"
    REJECT = "reject"


@dataclass(frozen=True)
class Proposal:
    """
    A single proposed tool call from the proposer (LLM).

    ``tool_id is None`` means the proposer signals completion (no more tools).
    """

    tool_id: str | None
    args: dict[str, Any] = field(default_factory=dict)

    def is_done(self) -> bool:
        return self.tool_id is None


@dataclass
class ToolDef:
    """Registry entry: identity, venue, and metadata for policy / execution."""

    tool_id: str
    venue: Venue
    idempotent: bool = False
    description: str = ""
    #: Tags for trace quotas (e.g. read, test). Counted after allow+execute.
    tags: tuple[str, ...] = ()


EventKind = Literal["classification", "step"]


@dataclass(frozen=True)
class ClassificationResult:
    """Output of task / prompt classification (feeds policy resolution)."""

    label: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """One append-only log line: classification record or a tool-loop step."""

    step_id: int
    proposal: Proposal
    decision: Decision
    reason: str = ""
    outcome: Any = None
    venue: Venue | None = None
    kind: EventKind = "step"
    classification: ClassificationResult | None = None

    def to_log_line(self) -> dict[str, Any]:
        line: dict[str, Any] = {
            "step_id": self.step_id,
            "event_kind": self.kind,
            "tool_id": self.proposal.tool_id,
            "args": self.proposal.args,
            "decision": self.decision.value,
            "reason": self.reason,
            "outcome": self.outcome,
            "venue": self.venue.value if self.venue else None,
        }
        if self.classification is not None:
            line["classification"] = {
                "label": self.classification.label,
                "confidence": self.classification.confidence,
                "metadata": dict(self.classification.metadata),
            }
        return line


AggregateMode = Literal["first", "majority"]
"""How to combine ``n > 1`` proposals before constraints (harness / variance control)."""


@dataclass
class ProfileConfig:
    """
    Serializable profile: allowed tools plus harness knobs (retries, consensus, step budget).

    Share as JSON (version control, internal registry, or paste into tickets). The control
    plane applies this when running a session with ``profile=<name>``.
    """

    name: str
    tools: list[str]
    description: str = ""
    # Harness: None means "use Session.max_steps / run() kwargs" where applicable.
    max_steps: int | None = None
    proposal_n: int = 1
    max_retries_on_no_consensus: int = 0
    aggregate: AggregateMode = "majority"
    # Optional metadata for teams (owner, schema URL, product area, etc.).
    labels: dict[str, str] = field(default_factory=dict)
    #: Minimum successful tool executions per tag (see :attr:`ToolDef.tags`), evaluated on the log.
    trace_requirements: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict (for persistence and sharing)."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileConfig:
        """Load from :meth:`to_dict` output or a hand-written JSON object."""
        name = str(data["name"])
        tools = list(data["tools"])
        description = str(data.get("description", ""))
        max_steps = data.get("max_steps")
        max_steps_i: int | None = None if max_steps is None else int(max_steps)
        proposal_n = int(data.get("proposal_n", 1))
        max_retries = int(data.get("max_retries_on_no_consensus", 0))
        agg_raw = str(data.get("aggregate", "majority"))
        if agg_raw not in ("first", "majority"):
            raise ValueError(f"aggregate must be 'first' or 'majority', got {agg_raw!r}")
        agg: AggregateMode = agg_raw  # narrowed
        labels = dict(data.get("labels") or {})
        tr_raw = data.get("trace_requirements") or {}
        if not isinstance(tr_raw, dict):
            raise TypeError("trace_requirements must be a dict[str, int]")
        trace_requirements = {str(k): int(v) for k, v in tr_raw.items()}
        return cls(
            name=name,
            tools=tools,
            description=description,
            max_steps=max_steps_i,
            proposal_n=proposal_n,
            max_retries_on_no_consensus=max_retries,
            aggregate=agg,
            labels=labels,
            trace_requirements=trace_requirements,
        )


@dataclass
class Session:
    """One run of the loop: identity, policy profile, and step budget."""

    session_id: str
    request: str
    profile: str
    max_steps: int = 10
    steps_taken: int = 0
    #: Set when a :class:`Classifier` + policy registry runs at session start.
    classification: ClassificationResult | None = None
    #: Merged profile + policy trace quotas for this run (min counts per tag).
    effective_trace_requirements: dict[str, int] = field(default_factory=dict)
