"""Example server-side tool implementations. Only the control plane runs these."""

from typing import Any


def run_add(a: float, b: float) -> float:
    return a + b


def run_search(query: str, corpus: str = "default") -> str:
    # Mock: in reality would call a search API
    return f"[{corpus}] results for: {query}"


def execute_server_tool(tool_id: str, args: dict[str, Any]) -> Any:
    """Dispatch to the right server tool. Control plane calls this only after constraint check."""
    if tool_id == "add":
        return run_add(args["a"], args["b"])
    if tool_id == "search":
        return run_search(args.get("query", ""), args.get("corpus", "default"))
    raise ValueError(f"Unknown server tool: {tool_id}")
