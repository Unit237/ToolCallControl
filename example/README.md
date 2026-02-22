# Example: Deterministic Tool-Calling Control Plane

Minimal implementation of the architecture in `../ARCHITECTURE.md`.

## What this does

- **Loop runner** owns the loop: propose → constrain → execute → log, until "done" or max steps.
- **Proposer** is a mock (returns a fixed sequence: add, search, done). Swap for a real LLM client.
- **Constraint pipeline** enforces an allowlist by profile (e.g. `safe_default` only allows `add` and `search`).
- **Tool registry** defines server tools (`add`, `search`) and a client tool (`run_terminal`). Profile selects which tools are in scope.
- **Executor** runs server tools; client tools would be dispatched (stubbed here).
- **Event log** is append-only, keyed by session. Every proposal, decision, and outcome is logged.

## Run

From the project root:

```bash
python3 -m example.main
```

Output: session id, step count, and the full event log (proposal, decision, outcome, venue per step).

## Layout

| File | Role |
|------|------|
| `model.py` | `Proposal`, `ToolDef`, `Event`, `Session`, enums |
| `event_log.py` | Append-only log by session |
| `tool_registry.py` | Tool definitions + profile → tool set |
| `tools.py` | Server-side tool implementations (`add`, `search`) |
| `constraint_pipeline.py` | Allowlist check before execute |
| `proposer.py` | Mock proposer (replace with LLM) |
| `executor.py` | Run server tools; client dispatch stubbed |
| `loop.py` | `LoopRunner`: create session, run loop, log every step |
| `main.py` | One session, print log |

## Extending

- **Real LLM:** Implement `propose(prompt, context, tool_ids, n)` in `proposer.py` to call your model and parse tool calls.
- **Consensus:** In `loop.py`, call proposer with `n>1`, then aggregate (e.g. majority) before `constraint_pipeline.check`.
- **Client execution:** In `executor.py`, for `venue=CLIENT` send the approved call to the client (e.g. over a stream), wait for `ToolOutcome`, then return it and log.
- **Persistence:** Replace in-memory `EventLog` with an append-only store (e.g. Postgres table keyed by `session_id`).
