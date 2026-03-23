"""Tool registry: map tool_id -> definition; profiles scope which tools are allowed."""

from __future__ import annotations

from typing import overload

from .model import ProfileConfig, ToolDef, Venue


def demo_tools() -> dict[str, ToolDef]:
    """Default tools for docs and ``python -m toolcallcontrol``."""
    server = {
        "add": ToolDef(
            tool_id="add",
            venue=Venue.SERVER,
            idempotent=True,
            description="Add two numbers",
            tags=("math",),
        ),
        "search": ToolDef(
            tool_id="search",
            venue=Venue.SERVER,
            idempotent=True,
            description="Search a corpus (demo stub)",
            tags=("read",),
        ),
    }
    client = {
        "run_terminal": ToolDef(
            tool_id="run_terminal",
            venue=Venue.CLIENT,
            idempotent=False,
            description="Run a shell command (client executes)",
            tags=("shell", "test"),
        ),
    }
    return {**server, **client}


def _coerce_profiles(
    profiles: dict[str, ProfileConfig | list[str]] | None,
    *,
    default_tools: dict[str, ToolDef],
) -> dict[str, ProfileConfig]:
    if profiles is None:
        return {
            "safe_default": ProfileConfig(name="safe_default", tools=["add", "search"]),
            "full_access": ProfileConfig(name="full_access", tools=list(default_tools.keys())),
        }
    out: dict[str, ProfileConfig] = {}
    for name, cfg in profiles.items():
        if isinstance(cfg, ProfileConfig):
            if cfg.name != name:
                raise ValueError(
                    f"profile key {name!r} must match ProfileConfig.name {cfg.name!r}"
                )
            out[name] = cfg
        else:
            out[name] = ProfileConfig(name=name, tools=list(cfg))
    return out


class ToolRegistry:
    """
    Registry with profile-based tool sets and optional per-profile harness settings.

    Pass ``tools`` and ``profiles`` to customize; otherwise uses :func:`demo_tools`.
    Each profile can be a :class:`ProfileConfig` (tools + retries, consensus, etc.) or a
    legacy list of tool ids (treated as :class:`ProfileConfig` with defaults).
    """

    def __init__(
        self,
        tools: dict[str, ToolDef] | None = None,
        profiles: dict[str, ProfileConfig | list[str]] | None = None,
    ) -> None:
        self._tools = dict(tools) if tools is not None else demo_tools()
        self._profiles = _coerce_profiles(profiles, default_tools=self._tools)

    def get(self, tool_id: str) -> ToolDef | None:
        return self._tools.get(tool_id)

    def list_for_profile(self, profile: str) -> list[ToolDef]:
        cfg = self._profiles.get(profile)
        ids = cfg.tools if cfg else list(self._tools.keys())
        return [self._tools[t] for t in ids if t in self._tools]

    def get_profile_config(self, name: str) -> ProfileConfig | None:
        """Return the named profile, or ``None`` if unknown."""
        return self._profiles.get(name)

    def list_profile_names(self) -> list[str]:
        return sorted(self._profiles.keys())

    @overload
    def register_profile(self, config: ProfileConfig, /) -> None: ...

    @overload
    def register_profile(self, name: str, tool_ids: list[str]) -> None: ...

    def register_profile(
        self,
        name_or_config: str | ProfileConfig,
        tool_ids: list[str] | None = None,
    ) -> None:
        """Add or replace a profile at runtime (useful for tests and dynamic policy)."""
        if isinstance(name_or_config, ProfileConfig):
            self._profiles[name_or_config.name] = name_or_config
            return
        if tool_ids is None:
            raise TypeError("register_profile(name, tool_ids) requires tool_ids")
        self._profiles[name_or_config] = ProfileConfig(name=name_or_config, tools=tool_ids)
