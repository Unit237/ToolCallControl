from toolcallcontrol import ConstraintPipeline, EventLog, LoopRunner, ToolRegistry


def test_demo_session_completes() -> None:
    log = EventLog()
    registry = ToolRegistry()
    runner = LoopRunner(log, registry, ConstraintPipeline(registry))
    session = runner.create_session("demo", max_steps=10)
    result = runner.run(session)

    assert result["session_id"]
    assert result["steps"] >= 3
    assert len(result["log"]) >= 3
    assert result["log"][-1]["tool_id"] is None  # done


def test_session_logs_allow_decisions() -> None:
    log = EventLog()
    registry = ToolRegistry()
    runner = LoopRunner(log, registry, ConstraintPipeline(registry))
    session = runner.create_session("x", profile="safe_default", max_steps=5)
    result = runner.run(session, proposal_n=1)
    assert any(e["decision"] == "allow" for e in result["log"])
