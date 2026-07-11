# Contributing

## Development Setup

**Requirements:** Python 3.12+. On macOS use Homebrew Python — the system Python (3.9) is not supported.

```bash
git clone https://github.com/your-org/virtual-silicon-validation-platform.git
cd virtual-silicon-validation-platform

/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the setup:

```bash
python --version        # must be 3.12+
virtual-silicon --help  # CLI must be available
pytest tests/ -q        # all tests must pass
```

## Code Standards

- Python 3.12 with full type annotations on all public functions and methods
- Ruff for linting (`E, F, W, I, N, UP, ANN, B, C4, SIM`): `ruff check src/ tests/`
- Mypy for type checking (src only): `mypy src/virtual_silicon/`
- Line length: 100 characters
- No `pass`-only implementations — all public APIs must be functional
- Docstrings on all public classes and methods

Notable rules to watch:

- **B904**: `raise X` inside `except` blocks must use `raise X from exc`
- **UP042**: use `StrEnum` not `class X(str, Enum)`
- **B905**: `zip()` needs `strict=False` or `strict=True`
- **ANN201**: return types required on all `src/` functions including properties

## Testing Requirements

- All new features need unit tests in `tests/unit/`
- All bug fixes need a regression test
- Coverage must stay at or above **85%** (`fail_under = 85` in `pyproject.toml`)
- Use fixed random seeds for determinism — pass `seed=42` to any component
- Use `sqlite:///:memory:` for database tests (the `temp_db` fixture)
- No physical hardware is required — the platform is fully virtual

## Running CI Locally

```bash
make ci
```

This runs: `lint → typecheck → test → coverage`.

You can also run individual steps:

```bash
make lint          # Ruff lint check
make lint-fix      # Auto-fix safe lint issues
make typecheck     # Mypy type check
make test          # All tests
make coverage      # Tests with HTML coverage report
```

## Submitting Changes

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make changes and add tests
3. Run `make ci` and ensure it passes
4. Open a pull request against `main`

PR descriptions should include: what changed, why, and how to test it.
