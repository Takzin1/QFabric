# Contributing to QFabric

QFabric is currently pre-alpha. Contributions should preserve a narrow,
hardware-agnostic core.

## Ground rules

- Do not add a vendor SDK to the core package.
- Do not claim hardware compatibility without reproducible tests and documentation.
- New adapters must declare capabilities explicitly.
- Validation failures should fail closed.
- Add tests for behavior changes.
- Keep digital-twin and proprietary inference logic outside this repository.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```
