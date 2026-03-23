"""Errors raised by the control plane."""


class ToolCallControlError(Exception):
    """Base exception for this library."""


class UnknownToolError(ToolCallControlError):
    """Raised when a tool_id is not in the registry."""


class ExecutionError(ToolCallControlError):
    """Raised when server tool execution fails."""


class ClassificationError(ToolCallControlError):
    """Raised when LLM classification output is missing or invalid."""
