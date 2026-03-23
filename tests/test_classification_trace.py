from toolcallcontrol import (
    CallableClassifier,
    ClassificationPolicyRegistry,
    ConstraintPipeline,
    EventLog,
    LoopRunner,
    MockClassifier,
    PolicyRule,
    ProfileConfig,
    Proposal,
    ToolDef,
    ToolRegistry,
    Venue,
    count_tags_from_events,
    trace_deficits,
    trace_requirements_met,
)
from toolcallcontrol.model import ClassificationResult, Decision, Event


def test_count_tags_from_events() -> None:
    tools = {
        "search": ToolDef("search", Venue.SERVER, tags=("read",)),
        "run_terminal": ToolDef("run_terminal", Venue.CLIENT, tags=("test",)),
    }
    reg = ToolRegistry(
        tools=tools,
        profiles={"p": ProfileConfig(name="p", tools=list(tools.keys()))},
    )
    ev = [
        Event(1, Proposal("search", {"q": "x"}), Decision.ALLOW, outcome="ok", kind="step"),
        Event(2, Proposal("run_terminal", {}), Decision.ALLOW, outcome="ok", kind="step"),
    ]
    c = count_tags_from_events(ev, reg)
    assert c["read"] == 1
    assert c["test"] == 1


def test_trace_requirements_met_and_deficits() -> None:
    from collections import Counter

    assert trace_requirements_met({"read": 2}, Counter({"read": 2, "test": 1}))
    assert not trace_requirements_met({"read": 2}, Counter({"read": 1}))
    d = trace_deficits({"read": 2, "test": 1}, Counter({"read": 1}))
    assert d["read"] == (1, 2)
    assert "test" in d


def test_profile_trace_requirements_allow_done_after_quota() -> None:
    reg = ToolRegistry(
        profiles={
            "strict": ProfileConfig(
                name="strict",
                tools=["add", "search"],
                trace_requirements={"read": 1},
            )
        }
    )
    log = EventLog()
    runner = LoopRunner(log, reg, ConstraintPipeline(reg))
    session = runner.create_session("task", profile="strict", max_steps=10)
    result = runner.run(session)
    assert result["log"][-1]["tool_id"] is None
    assert result["log"][-1]["decision"] == "allow"


def test_done_rejected_until_trace_met() -> None:
    class DoneThenTwoSearch:
        """Premature done, then two reads, then done."""

        def propose(self, prompt, context, tool_ids, *, n=1, session=None):
            step = len(context)
            if step == 0:
                return [Proposal(None, {})]
            if step <= 2:
                return [Proposal("search", {"query": "x"})]
            return [Proposal(None, {})]

    reg = ToolRegistry(
        profiles={
            "strict": ProfileConfig(
                name="strict",
                tools=["add", "search"],
                trace_requirements={"read": 2},
            )
        }
    )
    log = EventLog()
    runner = LoopRunner(log, reg, ConstraintPipeline(reg), proposer=DoneThenTwoSearch())
    session = runner.create_session("task", profile="strict", max_steps=10)
    result = runner.run(session)
    assert any(e.get("reason") == "trace_requirements_not_met" for e in result["log"])
    assert result["log"][-1]["tool_id"] is None
    assert result["log"][-1]["decision"] == "allow"


def test_classification_sets_profile_and_logs() -> None:
    reg = ToolRegistry(
        profiles={
            "safe_default": ProfileConfig(
                name="safe_default",
                tools=["add", "search"],
                trace_requirements={"read": 1},
            ),
        }
    )
    log = EventLog()
    runner = LoopRunner(
        log,
        reg,
        ConstraintPipeline(reg),
        classifier=MockClassifier("safe_default"),
        policy_registry=ClassificationPolicyRegistry(
            rules={"safe_default": PolicyRule(profile="safe_default")},
        ),
    )
    session = runner.create_session("irrelevant profile name", profile="full_access", max_steps=10)
    result = runner.run(session)
    assert result["log"][0]["event_kind"] == "classification"
    assert result["log"][0]["classification"]["label"] == "safe_default"
    assert session.profile == "safe_default"
    assert session.classification is not None


def test_policy_rule_merges_trace_requirements() -> None:
    reg = ToolRegistry(
        profiles={
            "base": ProfileConfig(
                name="base",
                tools=["add", "search"],
                trace_requirements={"read": 1},
            ),
        }
    )
    log = EventLog()

    class TwoSearchThenDone:
        def propose(self, prompt, context, tool_ids, *, n=1, session=None):
            if len(context) < 2:
                return [Proposal("search", {"query": "x"})]
            return [Proposal(None, {})]

    runner = LoopRunner(
        log,
        reg,
        ConstraintPipeline(reg),
        proposer=TwoSearchThenDone(),
        classifier=MockClassifier("bugfix"),
        policy_registry=ClassificationPolicyRegistry(
            rules={
                "bugfix": PolicyRule(profile="base", trace_requirements={"read": 2}),
            },
        ),
    )
    session = runner.create_session("fix it", profile="base", max_steps=10)
    result = runner.run(session)
    assert session.effective_trace_requirements.get("read") == 2
    assert result["log"][-1]["decision"] == "allow"


def test_callable_classifier_uses_llm_hook_not_keywords() -> None:
    def llm_classify(request: str) -> ClassificationResult:
        # Stand in for: response = client.chat.completions.create(...); parse JSON label
        return ClassificationResult(label="task_a", confidence=1.0, metadata={})

    cc = CallableClassifier(llm_classify)
    out = cc.classify("anything")
    assert out.label == "task_a"


def test_proposer_receives_session_with_classification() -> None:
    """Policy layer classifies once; proposer reads session — no duplicate keyword logic."""
    first_session: list = []

    class ProposerReadsSession:
        def propose(self, prompt, context, tool_ids, *, n=1, session=None):
            if len(context) == 0:
                first_session.append(session)
            if len(context) == 0:
                return [Proposal("search", {"query": "x"})]
            return [Proposal(None, {})]

    reg = ToolRegistry(
        profiles={
            "p": ProfileConfig(
                name="p",
                tools=["add", "search"],
                trace_requirements={"read": 1},
            ),
        }
    )
    log = EventLog()
    runner = LoopRunner(
        log,
        reg,
        ConstraintPipeline(reg),
        proposer=ProposerReadsSession(),
        classifier=MockClassifier("labeled"),
        policy_registry=ClassificationPolicyRegistry(
            rules={"labeled": PolicyRule(profile="p")},
        ),
    )
    session = runner.create_session("hello", profile="p", max_steps=5)
    runner.run(session)
    assert first_session and first_session[0] is session
    assert first_session[0].classification is not None
    assert first_session[0].classification.label == "labeled"
