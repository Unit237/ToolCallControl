"""Tool registry: map tool_id -> definition. Profile filters which tools are in scope."""

from typing import Optional

from .model import ToolDef, Venue

# Example server-side tools
SERVER_TOOLS = {
    "add": ToolDef(
        tool_id="add",
        venue=Venue.SERVER,
        idempotent=True,
        description="Add two numbers",
    ),
    "search": ToolDef(
        tool_id="search",
        venue=Venue.SERVER,
        idempotent=True,
        description="Search a corpus (mock)",
    ),
}

# Example client-side tool (would run in IDE / user env)
CLIENT_TOOLS = {
    "run_terminal": ToolDef(
        tool_id="run_terminal",
        venue=Venue.CLIENT,
        idempotent=False,
        description="Run a shell command (client executes)",
    ),
}

ALL_TOOLS = {**SERVER_TOOLS, **CLIENT_TOOLS}


class ToolRegistry:
    """Registry with profile-based tool sets."""

    def __init__(self) -> None:
        self._tools = dict(ALL_TOOLS)
        self._profiles: dict[str, list[str]] = {
            "safe_default": ["add", "search"],
            "full_access": list(self._tools.keys()),
        }

    def get(self, tool_id: str) -> Optional[ToolDef]:
        return self._tools.get(tool_id)

    def list_for_profile(self, profile: str) -> list[ToolDef]:
        ids = self._profiles.get(profile, list(self._tools.keys()))
        return [self._tools[t] for t in ids if t in self._tools]
