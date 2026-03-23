# Contributing

Thanks for your interest in **ToolCallControl**.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check src tests
python -m toolcallcontrol   # demo
```

Release artifacts: `python -m pip install build && python -m build` (produces `dist/*.whl` and `sdist`).

## Pull requests

- Keep the **control plane owns the loop and the log** invariant clear in changes.
- Add tests for new behavior.
- Update `CHANGELOG.md` under **Unreleased** for user-visible changes.

## Code style

- Python 3.10+ typing; public APIs should stay typed (`py.typed` is shipped).
