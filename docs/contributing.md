# Contributing

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Getting Started

```bash
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish
uv sync
```

This installs all dependencies including dev tools (pytest, ruff, mypy, coverage).

## Development Workflow

### Task Runner

SVG Polish uses [Poe the Poet](https://poethepoet.naber.dev/) for common tasks:

```bash
# Run all tests
uv run poe test

# Run tests with coverage report
uv run poe test-cov

# Lint with ruff
uv run poe lint

# Format with ruff
uv run poe format

# Type check with mypy
uv run poe typecheck

# Run all checks (lint + typecheck + test)
uv run poe check
```

### Running Tests

```bash
# All tests
uv run pytest tests/

# Specific test file
uv run pytest tests/test_fixtures.py

# Specific test class
uv run pytest tests/test_fixtures.py::TestFixtureComplexScene

# With coverage
uv run pytest tests/ --cov=svg_polish --cov-report=term-missing

# Verbose
uv run pytest tests/ -v
```

### Test Organization

```
tests/
├── test_optimizer.py          # 261 tests from original Scour test suite
├── test_public_api.py         # 19 tests for optimize(), optimize_file()
├── test_css.py                # 3 tests for CSS parser
├── test_parsers.py            # 32 tests for svg_regex.py and svg_transform.py
├── test_coverage.py           # 93 tests for edge cases and branches
├── test_remaining_coverage.py # 31 tests for final coverage gaps
├── test_fixtures.py           # 30 tests using real SVG fixtures
└── fixtures/                  # 150+ SVG test fixture files
```

**Total: 469 tests, 100% coverage.**

### Writing Tests

#### Using real SVG fixtures

Create an SVG file in `tests/fixtures/` and write tests against it:

```python
from pathlib import Path
from svg_polish import optimize

FIXTURES = Path(__file__).parent / "fixtures"

def test_my_feature():
    result = optimize((FIXTURES / "my-test.svg").read_text())
    assert "<rect" in result
```

#### Using inline SVG strings

For simple cases, pass SVG strings directly:

```python
from svg_polish import optimize

def test_color_shortening():
    result = optimize('<svg xmlns="http://www.w3.org/2000/svg">'
                      '<rect fill="#ff0000" width="10" height="10"/></svg>')
    assert 'fill="red"' in result
```

#### Testing with specific options

```python
from svg_polish.optimizer import scourString, parse_args

def test_with_viewboxing():
    options = parse_args(["--enable-viewboxing"])
    result = scourString(svg_string, options)
    assert "viewBox" in result
```

### SVG Fixture Guidelines

When creating test fixture SVGs:

1. **No `--` in comments** - XML forbids `--` inside `<!-- -->` comments
2. **Keep fixtures small** - Focus on the specific feature being tested
3. **Use descriptive filenames** - e.g., `gradient-dedup.svg`, `path-line-decompose-hv.svg`
4. **Include a brief comment** - Explain what the fixture tests

### Linting

SVG Polish uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

The legacy `optimizer.py` file has relaxed linting rules (see `pyproject.toml`).

### Type Checking

```bash
uv run mypy src/svg_polish/
```

SVG Polish ships with a `py.typed` marker for PEP 561 compliance.

## Pull Request Guidelines

1. All tests must pass (`uv run poe test`)
2. Coverage must stay at 100% (`uv run poe test-cov`)
3. No linting errors (`uv run poe lint`)
4. Type checking must pass (`uv run poe typecheck`)
5. Add tests for new functionality
6. Update documentation if adding user-facing features

## Project History

SVG Polish is a fork of [Scour](https://github.com/scour-project/scour), modernized for Python 3.10+. Key changes from the original:

- Removed Python 2 compatibility (`six`, `from __future__` imports)
- Modern packaging (`pyproject.toml`, `hatchling`, `uv`)
- Type annotations throughout
- 100% test coverage (up from ~70% in Scour)
- Clean public API (`optimize()`, `optimize_file()`)
- `pytest` instead of `unittest` runner

See [CHANGELOG.md](../CHANGELOG.md) for release notes.
