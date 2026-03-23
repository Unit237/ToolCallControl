from toolcallcontrol.aggregator import NoConsensus, majority_aggregate
from toolcallcontrol.model import Proposal


def test_majority_single() -> None:
    p = Proposal(tool_id="add", args={"a": 1})
    assert majority_aggregate([p]) is p


def test_majority_unanimous() -> None:
    p = Proposal(tool_id="add", args={"a": 1})
    assert majority_aggregate([p, p, p]) == p


def test_majority_tie() -> None:
    a = Proposal(tool_id="add", args={})
    b = Proposal(tool_id="search", args={})
    out = majority_aggregate([a, b])
    assert isinstance(out, NoConsensus)
