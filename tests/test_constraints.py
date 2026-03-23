from toolcallcontrol import ConstraintPipeline, Decision, Proposal, ToolRegistry


def test_profile_rejects_tool_not_in_profile() -> None:
    registry = ToolRegistry()
    registry.register_profile("only_add", ["add"])
    pipe = ConstraintPipeline(registry)
    decision, reason = pipe.check(Proposal(tool_id="search", args={}), "only_add")
    assert decision == Decision.REJECT
    assert "not in profile" in reason
