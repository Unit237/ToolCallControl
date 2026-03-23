"""Execute approved proposals: server-side here; client venue returns a stub outcome."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .builtin_tools import execute_server_tool
from .exceptions import UnknownToolError
from .model import Proposal, Venue
from .tool_registry import ToolRegistry

# Client dispatch: replace in integration (e.g. send over WebSocket, await ToolOutcome).
ClientHandler = Callable[[str, dict[str, Any]], Any]


def default_client_stub(tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Placeholder until the real client reports an outcome."""
    return {"status": "dispatched_to_client", "tool_id": tool_id, "args": args}


def execute(
    proposal: Proposal,
    registry: ToolRegistry,
    *,
    client_handler: ClientHandler | None = None,
    server_impl: Callable[[str, dict[str, Any]], Any] | None = None,
) -> tuple[Any, Venue | None]:
    """
    Run an approved proposal.

    - **Server** tools run via ``server_impl`` or :func:`builtin_tools.execute_server_tool`.
    - **Client** tools call ``client_handler`` or a safe stub that does not execute locally
      in the library process.
    """
    if proposal.is_done():
        return None, None

    tool_id = proposal.tool_id
    if not tool_id:
        return None, None

    tool_def = registry.get(tool_id)
    if not tool_def:
        raise UnknownToolError(f"Unknown tool: {tool_id}")

    if tool_def.venue == Venue.CLIENT:
        fn = client_handler or default_client_stub
        return fn(tool_id, proposal.args), Venue.CLIENT

    impl = server_impl or execute_server_tool
    return impl(tool_id, proposal.args), Venue.SERVER
