# QFabric AI coding guidance

Follow the repository's [AGENTS.md](../AGENTS.md) for scope,
minimal-change development and the quantum hardware safety boundaries.

Use existing modules and Python stdlib before adding dependencies or new
abstractions. **Do not shorten code by removing input validation,
provenance checks, tests, or plan-only restrictions.**

Before finishing, run `ruff check .` and `pytest` for behavioral changes;
describe any checks that could not be run. No external agent plugin or
lifecycle hooks are needed for these repo-local rules.
