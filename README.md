# ToolCallControl

**Deterministic tool-calling control plane for agent loops.**

The **agent LLM** proposes tool calls (via a **`Proposer`**). The control plane **decides** (policy), **dispatches** execution to **server** or **client** venues, and appends every step to an **audit-grade event log**. Same mental model as “Kubernetes for your tool loop”: one authority, delegated execution, one source of truth.

[![CI](https://github.com/your-org/ToolCallControl/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/ToolCallControl/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/toolcallcontrol.svg)](https://pypi.org/project/toolcallcontrol/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Where the LLMs run

| Role | API in this library | What it does |
|------|---------------------|--------------|
| **Agent** (main loop) | **`Proposer`** | Calls **your** chat completion (OpenAI-compatible, etc.), returns `Proposal(tool_id, args)` or “done”. **This is where the agent model runs** every step. |
| **Task classification** (optional) | **`Classifier`** + **`OpenAIClassifier`** | One structured call up front: label → **`ClassificationPolicyRegistry`** picks **`profile`** and merged **trace quotas**. Not the same model as the agent unless you wire it that way. |

The **control plane** (`LoopRunner`) does **not** call an LLM by itself — it calls **`Proposer`** and **`Classifier`** you provide.

---

## Where `bug_profile`, `write_profile`, … live

1. **`ProfileConfig` on `ToolRegistry`** — Register named profiles in code, e.g. `ToolRegistry(profiles={"bug_profile": ProfileConfig(name="bug_profile", tools=[...], trace_requirements={...}), ...})`.
2. **JSON on disk** — Same object: `profile_to_json` / `profile_from_json`, or a **bundle** `{"profiles": { "bug_profile": {...}, "write_profile": {...} }}` via `load_profile_bundle` / `dump_profile_bundle` (see `profiles` module).
3. **Classification routing** — **`PolicyRule`**: maps **classification label** → **profile name** + optional **trace_requirements** overrides. Built in Python with **`ClassificationPolicyRegistry`** (label → rule). There is **no** separate JSON loader for that map yet; keep it in code or load your own JSON and construct the registry at startup.

**Trace quotas** (`trace_requirements`: min counts per **tag**) live on **`ProfileConfig`** (and can be overridden per label via **`PolicyRule`**). Tags are declared on **`ToolDef.tags`**.

---

## Why

- **Governed execution** — Stochasticity stays in *proposal*; *what runs* is policy-bound.
- **One log** — Append-only events: classification (optional) → proposal → decision → outcome → venue.
- **Two venues, one loop** — **Server** tools and **Cursor-style client** tools; same policy and log.
- **Pluggable LLMs** — Bring your own **`Proposer`** (agent) and optional **`Classifier`**; optional **`OpenAIClassifier`** for a batteries-included classification call (`pip install 'toolcallcontrol[openai]'`).

Read the full design in [**ARCHITECTURE.md**](ARCHITECTURE.md).

---

## Install

```bash
pip install toolcallcontrol
```

Optional OpenAI SDK (for **`OpenAIClassifier`**):

```bash
pip install 'toolcallcontrol[openai]'
```

From source:

```bash
pip install -e ".[dev]"
```

---

## Quick start (minimal)

```python
from toolcallcontrol import (
    ConstraintPipeline,
    EventLog,
    LoopRunner,
    ToolRegistry,
)

log = EventLog()
registry = ToolRegistry()
runner = LoopRunner(log, registry, ConstraintPipeline(registry))

session = runner.create_session("Do something useful.", profile="safe_default")
result = runner.run(session)

print(result["log"])  # append-only list of dicts per step
```

**CLI demo:**

```bash
python -m toolcallcontrol
# or
tcc-demo
```

**Full end-to-end example** (offline mocks + optional live OpenAI): see [`examples/full_agent_example.py`](examples/full_agent_example.py).

---

## Package layout

| Module | Role |
|--------|------|
| `LoopRunner` | Loop: classify (optional) → propose → aggregate → constrain → execute → log; blocks **`done`** until **trace_requirements** met. |
| `EventLog` | Append-only log per `session_id` (in-memory default; swap for your DB). |
| `ToolRegistry` | `tool_id` → `ToolDef` (venue, tags, …) + **profiles** (`ProfileConfig`: tools, harness, **trace_requirements**). |
| `ConstraintPipeline` | Allow/reject before execution (allowlist by profile). |
| `Proposer` / `MockProposer` | **Agent LLM** adapter: `propose(..., session=session)` → `Proposal`s. |
| `Classifier` / `MockClassifier` / `CallableClassifier` / **`OpenAIClassifier`** | Task label → policy resolution. |
| `ClassificationPolicyRegistry` / `PolicyRule` | Label → **profile** + trace overrides. |
| `profiles` | JSON load/save for **`ProfileConfig`** (single file or bundle). |
| `majority_aggregate` | Optional **N-sample** consensus before constraints. |
| `execute` | Runs **server** tools or returns a **client** dispatch stub. |

---

## Roadmap

- Persistence adapters for `EventLog` (SQLAlchemy / SQLite recipe).
- JSON loader for **classification** rules (`PolicyRule` map), if the community wants it.
- Built-in streaming protocol sketches for client execution (WebSocket messages).
- More constraint types and golden-path testing helpers.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Links

- **Docs:** this README + [ARCHITECTURE.md](ARCHITECTURE.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

Replace `your-org` in badges and `pyproject.toml` `[project.urls]` with your GitHub org before publishing.
