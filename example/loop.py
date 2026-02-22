"""Loop runner: one session, step until done or cap. Owns the loop and the log."""

import uuid
from typing import Any

from .model import Decision, Event, Proposal, Session, Venue
from .event_log import EventLog
from .tool_registry import ToolRegistry
from .constraint_pipeline import ConstraintPipeline
from .proposer import propose as proposer_call
from .executor import execute


def _aggregate_one(proposals: list[Proposal]) -> Proposal:
    """Use first proposal as 'consensus' (for N=1 or simple majority)."""
    return proposals[0]


class LoopRunner:
    """
    Control plane loop: propose -> aggregate (if N>1) -> constrain -> execute -> log.
    Single authority over what runs; append-only log.
    """

    def __init__(
        self,
        event_log: EventLog,
        registry: ToolRegistry,
        constraint_pipeline: ConstraintPipeline,
    ) -> None:
        self.event_log = event_log
        self.registry = registry
        self.constraint_pipeline = constraint_pipeline

    def create_session(self, request: str, profile: str = "safe_default", max_steps: int = 10) -> Session:
        session_id = str(uuid.uuid4())[:8]
        return Session(session_id=session_id, request=request, profile=profile, max_steps=max_steps)

    def run(self, session: Session) -> dict[str, Any]:
        """Run the loop until done or max_steps. Returns final output and session summary."""
        context: list[dict] = []  # conversation + tool results so far

        while session.steps_taken < session.max_steps:
            step_id = session.steps_taken + 1
            tool_ids = [t.tool_id for t in self.registry.list_for_profile(session.profile)]

            # 1. Propose (mock: N=1)
            proposals = proposer_call(
                prompt=session.request,
                context=context,
                tool_ids=tool_ids,
                n=1,
            )
            accepted = _aggregate_one(proposals)

            # 2. Constrain
            decision, reason = self.constraint_pipeline.check(accepted, session.profile)

            outcome = None
            venue = None
            if decision == Decision.ALLOW and not accepted.is_done():
                outcome, venue = execute(accepted, self.registry)

            # 3. Log (append-only)
            event = Event(
                step_id=step_id,
                proposal=accepted,
                decision=decision,
                reason=reason,
                outcome=outcome,
                venue=venue,
            )
            self.event_log.append(session.session_id, event)

            session.steps_taken = step_id
            context.append({"proposal": accepted, "decision": decision, "outcome": outcome})

            if accepted.is_done():
                break

        return {
            "session_id": session.session_id,
            "steps": session.steps_taken,
            "log": self.event_log.read_as_dicts(session.session_id),
            "final_context": context,
        }
