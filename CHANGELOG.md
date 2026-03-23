# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-03-23

### Added

- **`OpenAIClassifier`** — optional `pip install 'toolcallcontrol[openai]'`; structured JSON classification.
- **`ClassificationError`** for invalid classifier output.
- **`examples/full_agent_example.py`** — offline mocks + live OpenAI agent wiring with real `tool_calls` → `Proposal` parsing.

## [0.2.1] - 2026-03-23

### Added

- **`Proposer.propose(..., session=session)`** — agent can read `session.classification` and `session.effective_trace_requirements` without duplicating classification.
- **`CallableClassifier`** for plugging in any `(request) -> ClassificationResult` (e.g. your LLM).

## [0.2.0] - 2026-03-23

### Added

- **`ProfileConfig.trace_requirements`**, **`ToolDef.tags`**, trace counting and **reject `done`** until quotas met.
- **`Classifier`** + **`ClassificationPolicyRegistry`** / **`PolicyRule`** (label → profile + trace overrides).
- **`Event.kind`** (`classification` | `step`), **`Session.classification`**, **`Session.effective_trace_requirements`**.
- JSON: **`trace_requirements`** on profiles; helpers unchanged (`profile_to_json`, bundles).

## [0.1.1] - 2026-03-23

### Added

- **`ProfileConfig`** harness fields and JSON load/save helpers (`profiles` module).

## [0.1.0] - 2026-02-22

### Added

- Initial open-source release: `LoopRunner`, append-only `EventLog`, `ToolRegistry`,
  `ConstraintPipeline`, pluggable `Proposer`, optional consensus via `majority_aggregate`,
  server vs client `Venue` in `execute`.
- `python -m toolcallcontrol` demo and `tcc-demo` console script.
- Architecture documentation (`ARCHITECTURE.md`).

[0.2.2]: https://github.com/your-org/ToolCallControl/releases/tag/v0.2.2
[0.2.1]: https://github.com/your-org/ToolCallControl/releases/tag/v0.2.1
[0.2.0]: https://github.com/your-org/ToolCallControl/releases/tag/v0.2.0
[0.1.1]: https://github.com/your-org/ToolCallControl/releases/tag/v0.1.1
[0.1.0]: https://github.com/your-org/ToolCallControl/releases/tag/v0.1.0
