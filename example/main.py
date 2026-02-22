#!/usr/bin/env python3
"""
Example: run one session through the control plane.
  propose -> constrain -> execute -> log  until done or max_steps.

Run from project root:  python -m example.main
"""

import json
from .event_log import EventLog
from .tool_registry import ToolRegistry
from .constraint_pipeline import ConstraintPipeline
from .loop import LoopRunner


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

    print("Session:", result["session_id"])
    print("Steps:", result["steps"])
    print("\nEvent log (append-only):")
    print(json.dumps(result["log"], indent=2))
    print("\nFinal context length:", len(result["final_context"]))


if __name__ == "__main__":
    main()
