"""Loop runner: the control plane owns the loop and the append-only log."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from .aggregator import NoConsensus, majority_aggregate
from .classifier import Classifier
from .constraint_pipeline import ConstraintPipeline
from .event_log import EventLog
from .executor import execute
from .model import (
    AggregateMode,
    ClassificationResult,
    Decision,
    Event,
    ProfileConfig,
    Proposal,
    Session,
)
from .policy import ClassificationPolicyRegistry
from .proposer import MockProposer, Proposer
from .proposer import propose as propose_fn
from .tool_registry import ToolRegistry
from .trace import count_tags_from_events, trace_deficits, trace_requirements_met

AggregateFn = Callable[[list[Proposal]], Proposal | NoConsensus]


def _builtin_aggregate(proposals: list[Proposal], mode: AggregateMode) -> Proposal | NoConsensus:
    """Combine ``n`` proposals unless a custom :class:`LoopRunner.aggregate` is set."""
    if len(proposals) == 1:
        return proposals[0]
    if mode == "first":
        return proposals[0]
    return majority_aggregate(proposals)


def _default_aggregate(proposals: list[Proposal]) -> Proposal | NoConsensus:
    if len(proposals) == 1:
        return proposals[0]
    return majority_aggregate(proposals)


class LoopRunner:
    """
    Control plane loop: propose → aggregate (optional) → constrain → execute → log.

    Single authority over what runs; append-only log per session.
    """

    def __init__(
        self,
        event_log: EventLog,
        registry: ToolRegistry,
        constraint_pipeline: ConstraintPipeline,
        *,
        proposer: Proposer | None = None,
        aggregate: AggregateFn | None = None,
        classifier: Classifier | None = None,
        policy_registry: ClassificationPolicyRegistry | None = None,
    ) -> None:
        self.event_log = event_log
        self.registry = registry
        self.constraint_pipeline = constraint_pipeline
        self.proposer = proposer or MockProposer()
        # Full override for proposal combination (ignores profile ``aggregate`` when set).
        self._user_aggregate = aggregate
        self.aggregate = aggregate or _default_aggregate
        self._classifier = classifier
        self._policy_registry = policy_registry
        if (classifier is None) ^ (policy_registry is None):
            raise ValueError("Provide both classifier and policy_registry, or neither")

    def create_session(
        self,
        request: str,
        profile: str = "safe_default",
        max_steps: int = 10,
    ) -> Session:
        session_id = str(uuid.uuid4())[:8]
        return Session(session_id=session_id, request=request, profile=profile, max_steps=max_steps)

    def _resolve_harness(
        self,
        session: Session,
        *,
        proposal_n: int | None,
        max_steps: int | None,
    ) -> tuple[ProfileConfig | None, int, int, AggregateMode, int]:
        cfg = self.registry.get_profile_config(session.profile)
        eff_n = proposal_n if proposal_n is not None else (cfg.proposal_n if cfg else 1)
        if eff_n < 1:
            raise ValueError("proposal_n must be >= 1")
        if max_steps is not None:
            eff_steps = max_steps
        elif cfg and cfg.max_steps is not None:
            eff_steps = cfg.max_steps
        else:
            eff_steps = session.max_steps
        if eff_steps < 1:
            raise ValueError("max_steps must be >= 1")
        mode: AggregateMode = (cfg.aggregate if cfg else "majority")
        retries = cfg.max_retries_on_no_consensus if cfg else 0
        return cfg, eff_n, eff_steps, mode, retries

    def _ensure_session_policy(self, session: Session) -> None:
        """Set ``session.profile`` (optional) and merged ``effective_trace_requirements``."""
        if self._classifier and self._policy_registry:
            cr = self._classifier.classify(session.request)
            session.classification = cr
            rule = self._policy_registry.resolve(cr.label)
            session.profile = rule.profile
            cfg = self.registry.get_profile_config(session.profile)
            eff = dict(cfg.trace_requirements if cfg else {})
            eff.update(rule.trace_requirements)
            session.effective_trace_requirements = eff
            self._log_classification(session, cr)
        else:
            cfg = self.registry.get_profile_config(session.profile)
            session.effective_trace_requirements = dict(cfg.trace_requirements if cfg else {})

    def _log_classification(self, session: Session, cr: ClassificationResult) -> None:
        ev = Event(
            step_id=0,
            proposal=Proposal(None, {}),
            decision=Decision.ALLOW,
            reason="classification",
            outcome=None,
            venue=None,
            kind="classification",
            classification=cr,
        )
        self.event_log.append(session.session_id, ev)

    def run(
        self,
        session: Session,
        *,
        proposal_n: int | None = None,
        max_steps: int | None = None,
    ) -> dict[str, Any]:
        """
        Run until the proposer signals done or the effective step budget.

        Harness defaults (samples per step, step cap, retries on no-consensus, aggregate
        mode) come from :class:`~toolcallcontrol.model.ProfileConfig` when the session
        names a registry profile. Keyword arguments override profile values for this run.
        """
        self._ensure_session_policy(session)
        _cfg, eff_proposal_n, eff_max_steps, agg_mode, no_consensus_retries = self._resolve_harness(
            session, proposal_n=proposal_n, max_steps=max_steps
        )

        context: list[dict[str, Any]] = []

        while session.steps_taken < eff_max_steps:
            step_id = session.steps_taken + 1
            tool_ids = [t.tool_id for t in self.registry.list_for_profile(session.profile)]

            def combine(proposals: list[Proposal]) -> Proposal | NoConsensus:
                if self._user_aggregate is not None:
                    return self._user_aggregate(proposals)
                return _builtin_aggregate(proposals, agg_mode)

            accepted: Proposal | None = None
            proposals: list[Proposal] = []
            agg: Proposal | NoConsensus | None = None
            attempt = 0
            while True:
                proposals = propose_fn(
                    session.request,
                    context,
                    tool_ids,
                    n=eff_proposal_n,
                    proposer=self.proposer,
                    session=session,
                )
                agg = combine(proposals)
                if not isinstance(agg, NoConsensus):
                    break
                if attempt >= no_consensus_retries:
                    break
                attempt += 1

            assert agg is not None
            if isinstance(agg, NoConsensus):
                event = Event(
                    step_id=step_id,
                    proposal=proposals[0],
                    decision=Decision.REJECT,
                    reason="no_consensus",
                    outcome={"proposals": [p for p in proposals]},
                    venue=None,
                )
                self.event_log.append(session.session_id, event)
                session.steps_taken = step_id
                context.append(
                    {"proposal": proposals[0], "decision": Decision.REJECT, "outcome": None}
                )
                continue

            accepted = agg

            decision, reason = self.constraint_pipeline.check(accepted, session.profile)

            outcome: Any = None
            venue = None
            if decision == Decision.ALLOW and accepted.is_done():
                counts = count_tags_from_events(
                    self.event_log.read(session.session_id),
                    self.registry,
                )
                req = session.effective_trace_requirements
                if req and not trace_requirements_met(req, counts):
                    deficits = trace_deficits(req, counts)
                    decision = Decision.REJECT
                    reason = "trace_requirements_not_met"
                    def_dict = {
                        k: {"have": have, "need": need} for k, (have, need) in deficits.items()
                    }
                    outcome = {
                        "required": dict(req),
                        "counts": dict(counts),
                        "deficits": def_dict,
                    }
            elif decision == Decision.ALLOW and not accepted.is_done():
                outcome, venue = execute(accepted, self.registry)

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
            ctx_row: dict[str, Any] = {
                "proposal": accepted,
                "decision": decision,
                "outcome": outcome,
            }
            if reason == "trace_requirements_not_met" and isinstance(outcome, dict):
                ctx_row["trace_feedback"] = outcome
            context.append(ctx_row)

            if accepted.is_done() and decision == Decision.ALLOW:
                break

        return {
            "session_id": session.session_id,
            "steps": session.steps_taken,
            "log": self.event_log.read_as_dicts(session.session_id),
            "final_context": context,
        }
