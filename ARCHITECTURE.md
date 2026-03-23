# Deterministic Tool-Calling Control Plane

**What we're building:** A control plane that owns the loop and the log for all tool use. LLMs propose actions; the control plane decides what runs, where it runs, and records every outcome. We support both **Cursor-style** interactions (client executes locally, reports back) and **server-executed** interactions (control plane or server runs tools). One system, one audit trail—execution venue is a choice.

---

## Architecture

```
                     ┌───────────────────┐
                     │      Client       │
                     │ - Sends request   │
                     │ - Receives output │
                     │   / events        │
                     │ - May execute     │
                     │   tools locally   │
                     │   (Cursor-style)  │
                     └─────────┬─────────┘
                               │
                               ▼
                     ┌───────────────────┐
                     │   Control Plane   │◀──────────────┐
                     │  (Loop Runtime)   │               │
                     │──────────────────│               │
                     │ - Owns tool-call  │               │
                     │   decisions       │               │
                     │ - Enforces policy │               │
                     │ - Logs every      │               │
                     │   decision +      │     ┌─────────┴─────────┐
                     │   outcome         │     │                   │
                     │ - Deterministic   │     ▼                   ▼
                     │   projections     │  Server tools    Client execution
                     └─────────┬─────────┘  (control plane   (client runs,
                               │             or server)       reports back)
                               ▼
                     ┌───────────────────┐
                     │      LLMs         │
                     │ Agent: Proposer   │
                     │ (each step)       │
                     │ Optional: Classi- │
                     │ fier (session     │
                     │ start)            │
                     └───────────────────┘
```

---

## Core Invariant

**The control plane owns the loop and the log.**  
LLMs suggest; the control plane decides what runs and records every decision and outcome. Execution can happen in two places:

- **Server** — Control plane (or a server it controls) runs the tool. Full determinism and replay from the log.
- **Client** — Client runs the tool locally (e.g. Cursor: terminal, file edits) and reports the result back. Control plane still decides (policy) and logs; we capture the interaction even though we don’t control the client environment.

So we **capture** both Cursor-like flows and server-side flows in one model: same loop, same policy, same event log. Where execution runs is a property of the tool or the session, not a different product.

---

## Execution Venues: Client vs Server

| Venue | Who runs the tool | What we guarantee |
|-------|-------------------|-------------------|
| **Server** | Control plane or server under its control | Full execution control, deterministic replay, same env every time. |
| **Client** | Client process (e.g. IDE, CLI) | We decide *what* runs (policy) and log the *outcome* the client reports. Audit and debugging; replay of client env is best-effort (e.g. replay decisions, compare reported results). |

Use server execution when you need strict reproducibility and control. Use client execution when the action must happen in the user’s environment (local edits, device access, Cursor-style workflows). Both are first-class in the same control plane.

---

## Components

| Component | Role |
|-----------|------|
| **Client** | Sends requests, receives output/events. May be thin (request/response only) or **thick** (executes tools locally and reports back, Cursor-style). Never bypasses the control plane for decisions or logging. |
| **Control Plane** | Loop runtime. Owns: receive proposal → apply constraints → decide run vs reject → dispatch to server or client → log decision + outcome → next step. Single authority for what runs and single owner of the event log. |
| **LLMs** | **Agent** via **Proposer** (each step). Optional **Classifier** at session start. Do not execute tools inside the model — execution is after policy. |
| **Tools** | Execution layer. May run on **server** (control plane or backend) or **client** (client executes and reports). Registry describes venue and semantics; control plane enforces policy for both. |

---

## Two LLM roles (agent vs classification)

The library does **not** embed a model server. Two different integrations are common:

| Role | Typical API | When it runs | Purpose |
|------|-------------|--------------|---------|
| **Agent** | Your **`Proposer`** implementation (e.g. OpenAI `chat.completions` with `tools`) | **Every step** of the loop | Propose the next tool call or signal **done** (`Proposal`). |
| **Classifier** (optional) | **`Classifier`** / **`OpenAIClassifier`** / **`CallableClassifier`** | **Once** at session start (before steps) | Emit a **label**; **`ClassificationPolicyRegistry`** resolves **profile** + merged **trace_requirements**. |

The **agent** is where the **main** LLM runs (tool loop). The **classifier** is a separate, usually smaller call for task routing. You can use the same provider and model for both, or not — it’s wiring, not a requirement.

**`LoopRunner`** passes **`session`** into **`Proposer.propose(..., session=session)`** so the agent can read **`session.classification`** and **`session.effective_trace_requirements`** (set by the control plane) **without** re-running classification or keyword heuristics in application code.

---

## Where profiles live (`bug_profile`, `write_profile`, …)

- **`ProfileConfig`** objects keyed by name on **`ToolRegistry`** (e.g. `"bug_profile"`, `"write_profile"`). Each profile lists **allowed `tools`**, **harness** (`max_steps`, `proposal_n`, consensus, no-consensus retries), and **trace_requirements** (minimum successful tool executions per **tag** on `ToolDef`).
- **Serialization** — Same data as **JSON**: `profile_to_json` / `profile_from_json`, or a **bundle** `{"profiles": { "name": { ... } } }` via `load_profile_bundle` / `dump_profile_bundle`. Good for git and review.
- **Label → profile** — **`ClassificationPolicyRegistry`** holds **`PolicyRule`** entries: `profile` name + optional **`trace_requirements`** overrides (merged on top of the profile). This map is **Python today**; load your own JSON at startup if you want a file-driven policy table.

Policy encodes **constraints** (allowlists, harness, **minimum evidence before** `done`). It does **not** encode a scripted step sequence (“turn 1 search, turn 2 search”) — the agent proposes freely; **trace_requirements** enforce **what must be true** on the log before termination.

---

## Mutability: What Engineers Can Change

We separate mutable extension points from immutable runtime guarantees.

| Component | Mutable? | How engineers interact | What you gain by mutating |
|-----------|----------|-------------------------|----------------------------|
| **Client** | Mostly immutable | Add/modify prompts, request metadata, select tool sets or profiles | Customization of input/output per client |
| **Control Plane Logic** | Partially mutable | Extend loops, add constraint types, termination rules, execution pipelines | New governance, loop behavior, safety policies |
| **Constraint Pipeline** | Mutable | Add/modify constraints (allowlists, denylists, rate limits, dry-run) | Enforce new policies, limit tools, manage safety dynamically |
| **Tool Registry** | Mutable | Add/modify tools, tool bundles, idempotency info, execution permissions | New capabilities, versioning, execution semantics |
| **LLM Providers** | Immutable from runtime POV | Swap providers, model version, or parameters | Different reasoning; planner behavior |
| **Event Log / State** | Append-only / deterministic | Not directly mutated; project or replay only | Auditable, replayable, deterministic execution |

**Implications:**

- **Control plane & constraint pipeline** — Mutating here changes how the loop behaves, not the raw LLM. You get new governance and safety without touching the proposer.
- **Tool registry** — Mutating here changes what can happen. Combine with constraints for contextual capability sets (e.g. `safe_default` vs `full_access`).
- **Event log / state** — Immutable. Enables deterministic replay and debugging. No rewriting history.
- **Client** — Mutable in request parameters and in which tools run locally (Cursor-style) vs on server. Clients only execute when the control plane has decided and logged; they don’t bypass the loop.
- **LLM** — Mutable only via model choice/version. No bit-level determinism; we only shape outputs probabilistically.

---

## Why This Design

1. **Governed stochasticity** — LLM reasoning stays flexible; execution is policy-bound and safe.
2. **Replayable loops** — Same control plane logic + constraints + tool registry + event log ⇒ reproducible execution for audit and debug.
3. **Extensibility** — New tools and policies without breaking the invariant that the control plane owns decisions and the log (whether execution is server or client).
4. **Operational reproducibility** — Same inputs and logic yield repeatable behavior relative to the logged event stream.
5. **Safe experimentation** — Add tools or policies incrementally without risking the deterministic core.

---

## Determinism Boundaries

| Where | Stochasticity | Control / Immutability |
|-------|----------------|-------------------------|
| **LLM proposals** | Allowed. Model output is probabilistic. | We only influence via prompts and model choice. |
| **Control plane** | None. Single owner of the loop and execution decisions. | Full control; loop logic and policy are the source of truth. |
| **Tool execution** | None in *deciding* what runs. | Control plane decides; execution may be server or client; every decision and reported outcome is logged. Server execution fully replayable; client execution auditable. |
| **Event log** | None. Append-only. | Deterministic projections; no mutation of past events. |

Stochasticity lives at the proposal layer; determinism and control live in the control plane and below.

---

## Optional Enhancements

- **Profiles / tool bundles** — Shipped: **`ProfileConfig`** on **`ToolRegistry`**, JSON bundle helpers, **trace_requirements** + **`ToolDef.tags`**, optional **classification** + **`PolicyRule`**.
- **JSON for classification rules** — File-driven loader for `ClassificationPolicyRegistry` (not in the library yet; construct from your own JSON).
- **Hookable prompt augmentation** — Pre/post system hooks for reasoning directives (e.g. “terminate after N steps”).
- **Idempotent tool execution** — Tools declare whether repeated calls with same inputs are safe; simplifies replay and determinism.

---

## Architecture ideas (proposals)

Ideas we are considering for the control plane. Not committed design; proposed for evaluation.

### Proposal: Consensus-based proposal aggregation

**Idea:** For a given step, the control plane does not treat a single LLM proposal as final. Instead it obtains **N proposals** (same prompt, N runs of the same model, or N different models), **aggregates** them (e.g. majority vote on tool + arguments, or "same proposal in ≥ K of N"), and treats the **consensus** as the accepted proposal. Only that accepted proposal goes through the existing pipeline (constraints, execute, log).

**Mechanics:**

- **Proposer side:** "Propose" can mean "produce N proposals" (same prompt, same or multiple models). Proposers stay stateless.
- **Control plane:** New step **before** constraints: **aggregate proposals** → one accepted proposal (e.g. majority/supermajority). If no consensus (e.g. no majority), policy decides: retry, escalate, or reject. Then apply existing constraints to the accepted proposal and proceed as today.
- **Policy knobs:** N (number of runs), K (minimum agreement, e.g. K-of-N), and whether to use same model N times or N different models. Can be set per tool, per profile, or per risk (e.g. sensitive tools require N ≥ 3 and supermajority).

**Why it fits:**

- The control plane still owns the final decision; we only change *how* the proposal is derived (aggregate then constrain), not who decides.
- As N grows, the accepted proposal converges to the **mode** of the proposal distribution (same model, same prompt). So we get a form of **convergence-stable** proposal: the decision stabilizes with N even though any single run is stochastic.
- Convergence can be used as a **confidence gate**: high agreement → auto-proceed; low agreement → require another round or human approval.

**Cost:** N× inference per step. N is a policy tradeoff (stability vs latency/cost).

---

**Does this make dumber models smarter?**

No, not in the sense of higher ceiling. Consensus does not add new knowledge or capability; it reduces **variance** by taking the mode over N samples. So:

- **Within capability:** If the model is usually right, the mode is often the correct tool/args. Voting then reduces random errors and makes behavior more **reliable** (fewer one-off mistakes). That can look "smarter" because outputs are more consistent and predictable.
- **Beyond capability:** If the model is usually wrong, the mode can be the **wrong** answer more consistently. You get stable failure, not better reasoning.
- **Summary:** Consensus makes proposals more **stable** and can reduce variance-induced errors; it does not make a weak model strong. It's best used when the model is already good enough and the goal is to avoid flaky or inconsistent tool choices, or when you want "low agreement" as a signal to escalate or retry rather than execute.

---

## Differentiation

- **Proposer + single authority over execution** — We make “LLM proposes, control plane decides and logs” the rule. Execution can be server or client (Cursor-style); the control plane still owns the loop and the audit trail. Others often add governance around frameworks where the agent still “does” execution without a unified model for client vs server.
- **Mutability as design** — We specify what is mutable vs immutable and why. Extension stays within bounds that preserve replay and determinism.
- **Replay from a minimal log** — Replay is driven by structured tool calls and outcomes (and minimal context), not full LLM I/O. The log is the source of truth.
- **The loop is the product** — The control plane is the loop. LLM and tools are inputs and outputs to it, not the other way around.

---

## Like Kubernetes for AI tool use

The same pattern that made Kubernetes the standard for container orchestration applies here: **a control plane that decides what runs, delegates execution, and keeps a single source of truth.** That analogy helps users understand the system and why it’s reliable and auditable.

### How the mapping works

| Kubernetes | This control plane |
|------------|--------------------|
| **Control plane** decides what runs; it does not run containers itself. | **Control plane** decides what runs; it may run tools (server) or instruct the **client** to run them. |
| You declare **desired state**; the control plane **reconciles** (schedules, instructs nodes). | The **proposer** (LLM) suggests a **desired action**; the control plane **allows or rejects**, then execution happens (server or client). |
| **Nodes** execute workloads; the control plane is the single authority. | **Server or client** executes tools; the control plane is the single authority. |
| **etcd** (and events) = source of truth for cluster state and history. | **Event log** = source of truth for what was decided and what ran. |
| Extensible via **CRDs**, controllers, admission. | Extensible via **constraints**, **tool registry**, **profiles**. |

So: one authority, a clear “desired vs actual” flow, execution delegated to other actors, and one place that owns the truth. **You already trust this pattern in infrastructure. This is that pattern for AI tool use.**

### Where we’re different (by design)

- **Domain:** Kubernetes orchestrates many workloads across a cluster over time. This orchestrates **one agent’s tool loop** (one session, one sequence of steps)—and, as below, can be extended to **multiple agents**.
- **Input:** Kubernetes gets **declarative specs** (YAML, desired state). Here we get **proposals** from an **LLM** (stochastic, step-by-step). The control plane still decides; the proposer is just the source of “desired next action.”
- **Scale of abstraction:** Kubernetes is cluster-wide. This is per-session (or per workflow when we add multi-agent). The **invariant** is the same: only the control plane authorizes execution and logs it.

### Multi-agent orchestration

The same control plane can **orchestrate multiple agents** without changing the core invariant: one authority, one log (or one log per session with a shared view), decide-then-execute.

**Ways to extend:**

| Model | How it works |
|-------|----------------|
| **Multiple sessions, one control plane** | One loop and one event stream per agent; the control plane runs all of them. Orchestration = which sessions exist, how they’re started/stopped, and how they interact (e.g. one session’s output is another’s input). Every tool call in every session is still proposed → constrained → executed → logged. |
| **Single loop, multi-agent proposals** | One loop, one log; at each step the proposal is “agent A does tool X” or “agent B does tool Y” or “hand off to B with context.” The proposer (or a meta-proposer / router) chooses which agent and what action; the control plane allows/rejects, dispatches, and logs. Agents are different namespaces or proposal sources. |
| **Workflow / DAG of agents** | Orchestration = a graph of agent steps. The control plane runs the workflow: each node is “run this agent’s loop until done or handoff,” then move to the next node. Each step is still propose → constrain → execute → log; the workflow decides which agent runs next and with what context. |

**What stays the same:** Only the control plane authorizes execution. One append-only log (per session or one unified log with session/agent ids). Constraints and tool registry can be per-agent or shared.

**What you add:** Notion of **agent identity** (or session = agent). **Routing / meta-proposer**: who acts next, with what context. Optional **handoffs**: one agent’s output (or a summary in the log) becomes another agent’s input.

So: **like Kubernetes, we have one control plane and delegated execution; like Kubernetes, we can scale from one “workload” (one agent) to many (multi-agent).** The architecture is the same; we extend what “proposal” and “session” mean.

### Why this helps (understanding and pitch)

- **Familiar mental model:** “Control plane that decides what runs and logs everything” is already how teams think about Kubernetes. Same idea, applied to AI tool use and agents.
- **Trust and operations:** “Single source of truth, append-only log, no execution without authorization” matches what operators expect from infrastructure. Easier to adopt and to sell to security and compliance.
- **Pitch in one line:** *“The control plane for AI tool use and agents—like Kubernetes for your LLM tool loops: one authority, one log, execution where you choose (server or client), and the same pattern for one agent or many.”*

---

## Implementation outline

How to build the control plane and integrate it with clients and tools.

### Reference implementation (Python library)

This repository ships **`toolcallcontrol`** (`src/toolcallcontrol/`): `LoopRunner`, `EventLog`, `ToolRegistry` with **`ProfileConfig`** (harness + **trace_requirements**), `ConstraintPipeline`, pluggable **`Proposer`** (agent LLM), optional **`Classifier`** / **`OpenAIClassifier`**, **`ClassificationPolicyRegistry`**, optional `majority_aggregate`, and `execute` for server vs client venues. Install with `pip install toolcallcontrol` (or `pip install -e .` from source). Run `python -m toolcallcontrol` for a demo session; see **`examples/full_agent_example.py`** for agent + classifier wiring. The table below maps concepts to that package; names may differ slightly in other languages.

### Core abstractions

| Component | Responsibility | Key interface |
|-----------|----------------|----------------|
| **Session** | One run of the loop (request → done or capped). Holds request, profile, tool set, and reference to the event log. | `create(request, profile) → session_id` |
| **Loop runner** | For each step: get proposal(s) → optionally aggregate → apply constraints → dispatch execution → log → decide next (continue/done/reject). | `step(session_id) → next_action` |
| **Proposer** | **Agent LLM**: call with current prompt/context; return one or N tool-call proposals (tool_id, args). Receives optional **`session`** (classification + trace policy). | `propose(prompt, context, tool_ids, n=1, session=None) → [Proposal]` |
| **Classifier** (optional) | **`OpenAIClassifier`** or custom **`Classifier`**: label for policy. | `classify(request) → ClassificationResult` |
| **Policy registry** (optional) | **`ClassificationPolicyRegistry`**: label → **`PolicyRule`** (profile + trace overrides). | `resolve(label) → PolicyRule` |
| **Aggregator** (optional) | Take N proposals, return consensus (e.g. majority) or “no consensus.” | `aggregate(proposals, policy) → AcceptedProposal | NoConsensus` |
| **Constraint pipeline** | Allowlist/denylist, rate limits, dry-run, venue checks. Input: accepted proposal. Output: allow | reject (reason). | `check(proposal, session) → Allow | Reject` |
| **Tool registry** | Map tool_id → definition (args schema, venue: server | client, idempotency). | `get(tool_id) → ToolDef`; `list(profile) → [ToolDef]` |
| **Executor** | Run tool on server (control plane calls impl) or send “approved call” to client and wait for reported outcome. | `execute(proposal, venue) → Outcome` (server) or `dispatch_to_client(proposal) → later Outcome` |
| **Event log** | Append-only. Each entry: step_id, proposal, decision (allow/reject), outcome (if executed), venue, timestamp. | `append(entry)`; `read(session_id) → [Entry]`; `replay(session_id) → re-run server steps` |

### Data flow (session start)

If **`classifier`** and **`policy_registry`** are set: **classify** request → set **`session.profile`** and **`session.effective_trace_requirements`** → append **classification** event to log. Harness (**`max_steps`**, **`proposal_n`**, …) is read from the resolved profile.

### Data flow (one step)

1. **Build context** — Conversation + tool results so far; tool list for this session (from registry + profile).
2. **Propose** — Call **agent** proposer (same prompt, N times if using consensus). Get one or N proposals. If proposal is **done**, enforce **trace_requirements** on the log before allowing termination.
3. **Aggregate** (if N > 1) — Run aggregator; if no consensus, apply policy (retry / escalate / reject) and log.
4. **Constrain** — Run constraint pipeline on accepted proposal. If reject, log and optionally feed back to loop (e.g. “tool not allowed” in next prompt).
5. **Execute** — If allow: lookup venue from registry; if server, run tool and get outcome; if client, send approved call to client, wait for reported outcome.
6. **Log** — Append (step_id, proposal, decision, outcome, venue).
7. **Next** — If proposal was “done” or max steps reached or termination policy says stop → return to client. Else → go to 1 with updated context.

### Client integration

- **Thin client:** Sends request, receives final output or stream of events. No tool execution; all tools run on server.
- **Thick client (Cursor-style):** Same, but for tools with venue=client:
  - Control plane sends “approved tool call” (tool_id, args) over the same channel (e.g. stream or callback).
  - Client runs the tool locally (e.g. run terminal command, apply file edit), then sends “outcome” (success/failure, result or error) back.
  - Control plane logs the outcome and continues the loop.
- **Protocol:** One bidirectional channel (e.g. HTTP stream, WebSocket, or long-poll). Messages: `Request` | `ApprovedToolCall(venue=client)` | `ToolOutcome` | `StreamEvent` | `FinalOutput`.

### Tech choices (suggested)

- **Language/runtime:** Any (Go, Rust, TypeScript, Python). Loop runner should be single-process or single-writer to the log for simplicity.
- **Event log:** Append-only store (e.g. Postgres table, SQLite, or event store). Keyed by session_id; ordering by step_id.
- **Proposer:** Stateless HTTP or SDK calls to LLM API(s). N runs can be parallel.
- **Tool execution (server):** Registry maps tool_id to a function or RPC. Run in sandbox or same process depending on trust.

---

## Utilization

How the system is used in practice: who calls it, for what, and what they get.

### As a platform (you operate the control plane)

- **You** run the control plane (loop runner, log, constraints, server-side tools). Clients are your users’ apps (IDEs, CLIs, backends).
- **Request:** Client sends “run this session” with prompt, profile/tool set, and optional client capabilities (e.g. “I can run terminal and file_edit”).
- **Response:** Stream of events (e.g. tool approved, outcome, message) and final output; or a single final result. Client never executes without an approved call from the control plane.
- **Use case:** SaaS for governed agentic workflows; audit and replay live in your infra.

### Cursor-style (thick client)

- **Client:** IDE or app that can run local tools (terminal, file edit, read file). User chats; client sends each turn to the control plane.
- **Flow:** User message → control plane runs loop → LLM proposes tool (e.g. “run `npm test`”) → control plane allows → control plane sends “approved: run terminal with args …” → client runs it locally and reports “success, exit 0” → control plane logs and continues → eventually “done” and final answer to user.
- **Use case:** Coding assistants, local dev tools, any product where actions must run in the user’s environment but you want one policy and one audit trail.

### Server-only agent

- **Client:** Thin. Sends task (e.g. “analyze this repo,” “draft email”). All tools run on the server (read repo, call API, write draft).
- **Flow:** Same loop; every tool has venue=server. Full determinism and replay on your side.
- **Use case:** Backend agents, data pipelines, internal automation with strict governance.

### Programmatic / API

- **Consumers:** Other services or scripts. POST “run session” with prompt, profile, tool set; get session_id and poll or stream for result. Optionally query event log by session_id for audit or replay.
- **Use case:** Embedding the control plane in products; CI/CD steps that run “approved” agent workflows; support tool that replays a user session for debugging.

### Multi-tenant / profiles

- **Tenant or product** selects a profile (e.g. `safe_default`, `full_access`, `cursor_editor`). Profile determines tool set (from registry) and constraint defaults (allowlists, N for consensus, max steps).
- Same control plane serves many tenants; policy and tool set are per session. Utilization is “run a session with this profile” plus “inspect or replay the log for this session.”

---

## Testing and convergence framework

**Convergence** here means: the system’s behavior converges to the **user’s desired behavior** for their use case. Not only “do N proposals agree” but “do outcomes match what the user wanted?” Below: how to specify desired behavior, how to measure it, and how to test for convergence.

### 1. Specifying desired behavior

The user (or product) defines what “right” looks like for a use case.

| Mechanism | What you define | Use when |
|-----------|------------------|-----------|
| **Acceptance criteria** | For a given request, what must be true at the end? (e.g. “file X contains Y,” “task marked done,” “user approved”). | Single-session success. |
| **Example runs** | Input (request + context) → expected tool sequence or expected final outcome. | Regression and golden-path tests. |
| **Reward / score** | A function of the event log or outcome (e.g. task completed, no disallowed tools, low step count). | Optimization and tuning. |
| **User feedback** | Explicit: thumbs up/down, “correct/incorrect.” Implicit: user accepted edit, user didn’t undo. | Learning desired behavior over time. |

Desired behavior can be **per request** (“this query should end with a summary”), **per profile** (“editor profile must never run terminal without user confirmation”), or **global** (“every execution must be logged”).

### 2. Measuring convergence

Convergence = “over some dimension, behavior gets closer to or more often matches desired behavior.”

| Dimension | What you measure | Convergence means |
|-----------|-------------------|--------------------|
| **Per run** | Did this session satisfy the acceptance criteria? | Success rate on a fixed test set. |
| **Over N runs (same request)** | Fraction of N runs that satisfy criteria (or that match the expected tool sequence). | As N grows, success rate stabilizes; or majority outcome equals desired outcome (aligns with consensus proposal). |
| **Over iterations (within a run)** | Each step: does the outcome get “closer” to the goal (e.g. tests pass, user said “good”)? | Run terminates in a “satisfactory” state (done, goal met) rather than cap or reject. |
| **Over tuning** | After changing prompts, constraints, or tools, does success rate (or average reward) on a test set improve? | System parameters converge to a configuration that meets the user’s bar for their use case. |

So: **convergence to desired behavior** = increasing (or stable high) rate of runs that meet the user’s criteria, and/or increasing reward when you tune the system.

### 3. Testing

| Test type | What it does | How it uses the framework |
|-----------|--------------|----------------------------|
| **Replay** | Re-run a session from the event log (server steps only). Same log ⇒ same execution. | Validates determinism and that the control plane reproduces past behavior. |
| **Regression** | Fixed set of (request, context) → run session; compare outcome or tool sequence to expected (or to last approved baseline). | Ensures changes to prompts/constraints/tools don’t break desired behavior. |
| **Property** | Invariants that must hold for every run (e.g. “every execution has a preceding allow decision,” “log is append-only,” “no tool outside profile”). | Ensures control-plane guarantees hold. |
| **Convergence (over N runs)** | Same request run N times; measure how often outcome matches desired behavior (or how often accepted proposal equals the “correct” one). | Quantifies stability and alignment with user intent; can gate on “success rate ≥ X%.” |
| **Convergence (over tuning)** | Define reward/criteria; tune (prompts, profiles, constraints); re-run test set and measure reward or success rate. | Validates that the system can be improved toward the user’s desired behavior. |

Tests can be **automated** (CI: replay, regression, property, optional convergence gate) and **manual or semi-automated** (human labels or feedback as desired-behavior signal for tuning).

### 4. Minimal workflow

1. **Define** desired behavior for the use case: acceptance criteria, example runs, or reward.
2. **Implement** checks: “did this log/outcome satisfy criteria?” or “reward(log).”
3. **Run** tests: replay, regression, property. Optionally: run same request N times and measure success rate (convergence over runs).
4. **Tune** (if needed): adjust prompts, constraints, or tools; re-run tests. Iterate until success rate or reward meets the user’s bar (convergence over tuning).
5. **Gate** (optional): in CI, require “replay passes, property tests pass, regression suite passes, and (if used) convergence success rate ≥ threshold.”

This gives a clear **testing and convergence framework** where “convergence” is explicitly “converging to the user’s desired behavior” for their use case, measured and tested as above.

---

## Summary

We are building the **deterministic tool-calling control plane**: the place where tool use is governed, logged, and—where execution is server-side—replayed. LLMs propose; the control plane decides and records. We support both **Cursor-style** interactions (client executes, we capture) and **server-executed** interactions (we run and replay). One loop, one log, two execution venues. That’s what makes this system clear, safe, and reproducible across environments.
