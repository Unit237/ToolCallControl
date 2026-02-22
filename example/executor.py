"""Executor: run server tools only. Client tools would be dispatched; client reports outcome."""

from typing import Any, Optional

from .model import Proposal, Venue
from .tool_registry import ToolRegistry
from . import tools


def execute(proposal: Proposal, registry: ToolRegistry) -> tuple[Any, Optional[Venue]]:
    """
    Execute the approved proposal. Server tools run here; client tools would be
    sent to the client and we'd wait for ToolOutcome (not implemented in this example).
    """
    if proposal.is_done():
        return None, None

    tool_def = registry.get(proposal.tool_id)
    if not tool_def:
        raise ValueError(f"Unknown tool: {proposal.tool_id}")

    if tool_def.venue == Venue.CLIENT:
        # In a real implementation: send to client, return when client reports outcome
        return {"status": "dispatched_to_client", "tool_id": proposal.tool_id}, Venue.CLIENT

    outcome = tools.execute_server_tool(proposal.tool_id, proposal.args)
    return outcome, Venue.SERVER
