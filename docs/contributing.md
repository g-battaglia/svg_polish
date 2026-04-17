# Contributing

## Development setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`

### Bootstrap

```bash
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish
uv sync
```

This installs runtime dependencies (`defusedxml`) plus the dev tooling
(`pytest`, `pytest-benchmark`, `coverage`, `ruff`, `mypy`, `poethepoet`).
The `[fast]` extra is reserved for the v1.x `lxml` backend and is
inert in v1.0.

## Workflow

`svg_polish` uses [Poe the Poet](https://poethepoet.naber.dev/) for
common tasks:

```bash
uv run poe test          # full test suite
uv run poe test-cov      # with HTML coverage report
uv run poe lint          # ruff lint
uv run poe format        # ruff format
uv run poe typecheck     # mypy --strict
uv run poe check         # all of the above

uv run poe bench         # save a performance baseline
uv run poe bench-compare # compare current run vs baseline (5% tolerance)
```

The check gate must be green for every PR:

- `pytest` — 100 % line coverage required.
- `mypy --strict` — zero errors.
- `ruff check` and `ruff format --check` — clean.

## Running tests

```bash
# Full suite (excluding benchmarks)
uv run pytest tests/

# A single file
uv run pytest tests/test_security.py

# A single test
uv run pytest tests/test_options.py::test_options_immutable

# With coverage
uv run pytest tests/ --cov=svg_polish --cov-report=term-missing

# Benchmarks (opt-in via marker)
uv run pytest tests/benchmarks/ -m benchmark --benchmark-only
```

The default `pytest` invocation excludes the `benchmark` marker — see
`pyproject.toml` `[tool.pytest.ini_options]`.

## Test suites

```
tests/
├── test_optimizer.py        # core optimisation behaviour
├── test_public_api.py       # optimize, optimize_path, optimize_with_stats, …
├── test_options.py          # OptimizeOptions validation, immutability, defaults
├── test_exceptions.py       # SvgPolishError hierarchy, attributes
├── test_security.py         # defusedxml posture, XXE / billion-laughs / oversize
├── test_concurrency.py      # threaded optimisation, deterministic output
├── test_float_engine.py     # decimal vs float engine isolation
├── test_modern_api.py       # OptimizeResult / OptimizeOptions surface
├── test_performance.py      # caching invariants
├── test_robustness.py       # malformed inputs
├── test_fixtures.py         # 150+ real-world SVG fixtures
├── test_parsers.py          # svg_regex / svg_transform
├── test_css.py              # css.py
├── test_coverage.py         # edge-case branches
├── benchmarks/
│   ├── conftest.py          # session-scoped fixture generator
│   └── test_perf.py         # pytest-benchmark suite
└── fixtures/                # SVG inputs
```

## Writing tests

### Fixture-driven

Drop an SVG into `tests/fixtures/` and assert against it:

```python
from pathlib import Path
from svg_polish import optimize

FIXTURES = Path(__file__).parent / "fixtures"

def test_my_feature() -> None:
    result = optimize((FIXTURES / "my-test.svg").read_text())
    assert "<rect" in result
```

### Inline SVG strings

```python
from svg_polish import optimize

def test_color_shortening() -> None:
    result = optimize(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect fill="#ff0000" width="10" height="10"/></svg>'
    )
    assert 'fill="red"' in result
```

### With `OptimizeOptions`

```python
from svg_polish import optimize, OptimizeOptions

def test_with_viewboxing() -> None:
    opts = OptimizeOptions(enable_viewboxing=True)
    assert "viewBox" in optimize(svg, opts)
```

## Fixture guidelines

When adding test SVGs:

1. **No `--` in comments** — XML forbids `--` inside `<!-- -->`.
2. **Keep fixtures small** — focus on the specific feature.
3. **Use descriptive filenames** — `gradient-dedup.svg`,
   `path-line-decompose-hv.svg`.
4. **Add a brief comment** explaining what the fixture exercises.
5. **No consumer-specific names** — fixtures describe a profile
   (`dense-chart-100kb`), not an origin.

## Linting

```bash
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .
```

The legacy `optimizer.py` orchestrator has slightly relaxed rules
(see `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml`) because
it owns the long pipeline `if`/`elif` chain.

## Type checking

```bash
uv run mypy src/svg_polish/
```

`mypy --strict` is mandatory. The package ships `py.typed` (PEP 561),
so user code that imports from `svg_polish` is also fully type-checked.

## Pull request checklist

1. `uv run poe check` is green.
2. Coverage is still at 100 %.
3. Benchmarks (`uv run poe bench-compare`) within 5 % of the saved
   baseline, or the regression is documented and justified.
4. Any new public symbol is exported from `svg_polish/__init__.py` and
   documented in `docs/api.md`.
5. New behaviour gets a test; new options get a `test_options.py`
   validation case.
6. `CHANGELOG.md` updated under the next-version heading.

## Project history

See [`README.md`](../README.md) and [`CHANGELOG.md`](../CHANGELOG.md)
for the v1.0 release notes and Scour heritage. The architectural
rebuild is documented in [`docs/architecture.md`](architecture.md).
