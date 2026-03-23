from toolcallcontrol import (
    ConstraintPipeline,
    EventLog,
    LoopRunner,
    ProfileConfig,
    ToolRegistry,
    load_profile_bundle,
    profile_from_json,
    profile_to_json,
)


def test_profile_config_json_roundtrip() -> None:
    p = ProfileConfig(
        name="team_cursor",
        tools=["add", "search"],
        description="Demo",
        max_steps=8,
        proposal_n=3,
        max_retries_on_no_consensus=1,
        aggregate="first",
        labels={"team": "platform"},
        trace_requirements={"read": 1, "test": 1},
    )
    s = profile_to_json(p)
    q = profile_from_json(s)
    assert q == p


def test_profile_bundle_roundtrip() -> None:
    from toolcallcontrol import dump_profile_bundle

    a = ProfileConfig(name="a", tools=["add"], proposal_n=2)
    b = ProfileConfig(name="b", tools=["search"], aggregate="majority")
    raw = dump_profile_bundle({"a": a, "b": b})
    loaded = load_profile_bundle(raw)
    assert loaded["a"] == a
    assert loaded["b"] == b


def test_registry_rejects_name_mismatch() -> None:
    bad = ProfileConfig(name="other", tools=["add"])
    try:
        ToolRegistry(profiles={"good": bad})
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "must match" in str(e)


def test_harness_from_profile_first_aggregate() -> None:
    """With aggregate=first, differing parallel proposals still pick the first."""
    from toolcallcontrol.proposer import Proposal

    class SplitProposer:
        def propose(self, prompt, context, tool_ids, *, n=1, session=None):
            step = len(context)
            if step == 0 and n == 2:
                return [
                    Proposal(tool_id="add", args={"a": 1, "b": 0}),
                    Proposal(tool_id="add", args={"a": 2, "b": 0}),
                ]
            return [Proposal(tool_id="add", args={"a": 1, "b": 1})] * max(n, 1)

    reg = ToolRegistry(
        profiles={
            "h": ProfileConfig(
                name="h",
                tools=["add", "search"],
                proposal_n=2,
                aggregate="first",
            )
        }
    )
    log = EventLog()
    runner = LoopRunner(log, reg, ConstraintPipeline(reg), proposer=SplitProposer())
    session = runner.create_session("x", profile="h", max_steps=1)
    result = runner.run(session)
    # First step: two proposals disagree on args → first wins → add executes
    assert result["log"][0]["args"] == {"a": 1, "b": 0}


def test_no_consensus_retries_from_profile() -> None:
    """Retries re-sample before emitting a no_consensus log line."""
    from toolcallcontrol.proposer import Proposal

    class FlakyProposer:
        def __init__(self) -> None:
            self.calls = 0

        def propose(self, prompt, context, tool_ids, *, n=1, session=None):
            self.calls += 1
            if self.calls == 1:
                return [
                    Proposal(tool_id="add", args={"a": 1, "b": 0}),
                    Proposal(tool_id="add", args={"a": 2, "b": 9}),
                ]
            return [Proposal(tool_id="add", args={"a": 3, "b": 4})] * 2

    reg = ToolRegistry(
        profiles={
            "r": ProfileConfig(
                name="r",
                tools=["add", "search"],
                proposal_n=2,
                max_retries_on_no_consensus=1,
                aggregate="majority",
            )
        }
    )
    log = EventLog()
    p = FlakyProposer()
    runner = LoopRunner(log, reg, ConstraintPipeline(reg), proposer=p)
    session = runner.create_session("x", profile="r", max_steps=1)
    result = runner.run(session)
    assert not any(e.get("reason") == "no_consensus" for e in result["log"])
    assert result["log"][0]["tool_id"] == "add"
