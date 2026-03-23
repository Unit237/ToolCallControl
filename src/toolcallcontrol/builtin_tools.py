"""Reference server-side tool implementations used by the default demo registry."""

from __future__ import annotations

from typing import Any

from .exceptions import ExecutionError


def run_add(a: float, b: float) -> float:
    return a + b


def run_search(query: str, corpus: str = "default") -> str:
    return f"[{corpus}] results for: {query}"


def execute_server_tool(tool_id: str, args: dict[str, Any]) -> Any:
    """Dispatch to a built-in server tool after policy approval."""
    if tool_id == "add":
        return run_add(args["a"], args["b"])
    if tool_id == "search":
        return run_search(args.get("query", ""), args.get("corpus", "default"))
    raise ExecutionError(f"Unknown server tool: {tool_id}")
