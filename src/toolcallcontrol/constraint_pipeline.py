"""Constraint pipeline: allowlist by profile; extend with more checks."""

from .model import Decision, Proposal
from .tool_registry import ToolRegistry


class ConstraintPipeline:
    """Check a proposal against policy before execution."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def check(self, proposal: Proposal, profile: str) -> tuple[Decision, str]:
        if proposal.is_done():
            return Decision.ALLOW, ""

        tool_def = self.registry.get(proposal.tool_id or "")
        if not tool_def:
            return Decision.REJECT, f"Unknown tool: {proposal.tool_id}"

        allowed = [t.tool_id for t in self.registry.list_for_profile(profile)]
        if proposal.tool_id not in allowed:
            return Decision.REJECT, f"Tool {proposal.tool_id} not in profile {profile}"

        return Decision.ALLOW, ""
