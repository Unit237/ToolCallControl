"""Data model for the control plane: proposals, tools, events, sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Venue(str, Enum):
    SERVER = "server"
    CLIENT = "client"


class Decision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"


@dataclass(frozen=True)
class Proposal:
    """What the LLM proposed: a tool call or 'done'."""

    tool_id: Optional[str]  # None means "done", no more tools
    args: dict[str, Any] = field(default_factory=dict)

    def is_done(self) -> bool:
        return self.tool_id is None


@dataclass
class ToolDef:
    """Registry entry for a tool: schema, venue, idempotency."""

    tool_id: str
    venue: Venue
    idempotent: bool = False
    description: str = ""


@dataclass
class Event:
    """One append-only log entry for a step."""

    step_id: int
    proposal: Proposal
    decision: Decision
    reason: str = ""  # e.g. reject reason
    outcome: Any = None  # result or error from execution (if allowed)
    venue: Optional[Venue] = None

    def to_log_line(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_id": self.proposal.tool_id,
            "args": self.proposal.args,
            "decision": self.decision.value,
            "reason": self.reason,
            "outcome": self.outcome,
            "venue": self.venue.value if self.venue else None,
        }


@dataclass
class Session:
    """One run: request, profile, and reference to the log."""

    session_id: str
    request: str
    profile: str
    max_steps: int = 10
    steps_taken: int = 0
