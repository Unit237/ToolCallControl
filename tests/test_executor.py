import pytest

from toolcallcontrol.builtin_tools import execute_server_tool
from toolcallcontrol.exceptions import ExecutionError
from toolcallcontrol.executor import execute
from toolcallcontrol.model import Proposal, Venue
from toolcallcontrol.tool_registry import ToolRegistry


def test_server_add() -> None:
    r = ToolRegistry()
    out, venue = execute(Proposal(tool_id="add", args={"a": 2, "b": 3}), r)
    assert out == 5
    assert venue == Venue.SERVER


def test_unknown_server_tool_raises() -> None:
    with pytest.raises(ExecutionError):
        execute_server_tool("nope", {})
