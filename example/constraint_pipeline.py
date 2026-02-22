"""Constraint pipeline: allowlist by profile, optional denylist. Control plane calls this before execute."""

from .model import Decision, Proposal, Venue
from .tool_registry import ToolRegistry


class ConstraintPipeline:
    """Check a proposal against policy. Returns allow or reject with reason."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def check(self, proposal: Proposal, profile: str) -> tuple[Decision, str]:
        if proposal.is_done():
            return Decision.ALLOW, ""

        tool_def = self.registry.get(proposal.tool_id)
        if not tool_def:
            return Decision.REJECT, f"Unknown tool: {proposal.tool_id}"

        allowed = [t.tool_id for t in self.registry.list_for_profile(profile)]
        if proposal.tool_id not in allowed:
            return Decision.REJECT, f"Tool {proposal.tool_id} not in profile {profile}"

        return Decision.ALLOW, ""
