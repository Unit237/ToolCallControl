"""``python -m toolcallcontrol`` — print one demo session and event log."""

from __future__ import annotations

import json

from .constraint_pipeline import ConstraintPipeline
from .event_log import EventLog
from .loop import LoopRunner
from .tool_registry import ToolRegistry


def main() -> None:
    log = EventLog()
    registry = ToolRegistry()
    constraints = ConstraintPipeline(registry)
    runner = LoopRunner(log, registry, constraints)

    session = runner.create_session(
        request="Compute 2+3 and then search for 'control plane'.",
        profile="safe_default",
        max_steps=10,
    )

    result = runner.run(session)

    print("ToolCallControl demo session")
    print("session_id:", result["session_id"])
    print("steps:", result["steps"])
    print("\nAppend-only event log:")
    print(json.dumps(result["log"], indent=2))


if __name__ == "__main__":
    main()
