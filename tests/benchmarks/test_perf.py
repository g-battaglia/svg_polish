"""Performance benchmarks for the optimisation pipeline.

Skipped by default (``addopts = -m 'not benchmark'`` in pyproject.toml);
opt in via ``poe bench`` or ``pytest tests/benchmarks/ --benchmark-only``.

Each test reads a session-scoped dense fixture (~50-100 KB SVG) once
outside the timed call, then measures one full ``optimize`` invocation
under different option combinations:

* default Decimal engine — the lossless baseline,
* ``decimal_engine="float"`` — opt-in faster path,
* ``shorten_ids=True`` — the heaviest combined pass.

Results are saved with ``--benchmark-save=baseline`` and replayed via
``--benchmark-compare=baseline --benchmark-compare-fail=mean:5%`` so
regressions of more than 5 % fail CI when this is wired up post-1.0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from svg_polish import OptimizeOptions, optimize


def _read(fixtures: dict[str, Path], name: str) -> str:
    """Read a fixture once before the timed call so I/O isn't measured."""
    return fixtures[name].read_text()


@pytest.mark.benchmark(group="dense-svg-decimal")
@pytest.mark.parametrize(
    "fixture",
    [
        "dense-chart-50kb.svg",
        "dense-chart-100kb.svg",
        "dense-paths-medium.svg",
    ],
)
def test_optimize_dense_decimal(
    benchmark: pytest.FixtureRequest,
    benchmark_fixtures: dict[str, Path],
    fixture: str,
) -> None:
    """Default lossless engine on dense fixtures."""
    svg = _read(benchmark_fixtures, fixture)
    result = benchmark(optimize, svg)  # type: ignore[operator]
    assert result.startswith("<")
    assert len(result) <= len(svg)


@pytest.mark.benchmark(group="dense-svg-float")
@pytest.mark.parametrize(
    "fixture",
    [
        "dense-chart-50kb.svg",
        "dense-chart-100kb.svg",
        "dense-paths-medium.svg",
    ],
)
def test_optimize_dense_float(
    benchmark: pytest.FixtureRequest,
    benchmark_fixtures: dict[str, Path],
    fixture: str,
) -> None:
    """Opt-in float engine — reference for the ~3-5x speedup target."""
    svg = _read(benchmark_fixtures, fixture)
    options = OptimizeOptions(decimal_engine="float")
    result = benchmark(optimize, svg, options)  # type: ignore[operator]
    assert result.startswith("<")
    assert len(result) <= len(svg)


@pytest.mark.benchmark(group="dense-svg-shorten-ids")
@pytest.mark.parametrize(
    "fixture",
    [
        "dense-chart-100kb.svg",
    ],
)
def test_optimize_dense_shorten_ids(
    benchmark: pytest.FixtureRequest,
    benchmark_fixtures: dict[str, Path],
    fixture: str,
) -> None:
    """Heaviest pass combination — used for the ≤30 ms target check."""
    svg = _read(benchmark_fixtures, fixture)
    options = OptimizeOptions(shorten_ids=True, decimal_engine="float")
    result = benchmark(optimize, svg, options)  # type: ignore[operator]
    assert result.startswith("<")
