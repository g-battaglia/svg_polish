"""Performance tests verifying algorithmic complexity.

These tests check that key operations scale as expected (e.g. O(n) not O(n²))
and that the optimizer handles large inputs without timing out.

When run under coverage instrumentation (``pytest --cov``) the wall-clock
thresholds are skipped, since coverage tracing slows execution by 5–10×
and would produce false-positive failures.
"""

from __future__ import annotations

import sys
import time

import pytest

from svg_polish.optimizer import scourString


def _coverage_active() -> bool:
    """Return True if ``coverage`` (or ``pytest-cov``) is currently tracing."""
    return "coverage" in sys.modules and getattr(sys, "gettrace", lambda: None)() is not None


pytestmark = pytest.mark.skipif(
    _coverage_active(), reason="wall-clock thresholds are unreliable under coverage tracing"
)


def _time_it(func: object, iterations: int = 1) -> float:
    """Time a callable in seconds."""
    start = time.perf_counter()
    for _ in range(iterations):
        if callable(func):
            func()
    return time.perf_counter() - start


class TestPathScaling:
    """clean_path must scale linearly with segment count."""

    def test_clean_path_linear_time(self) -> None:
        """Path optimization should scale roughly linearly, not quadratically.

        If clean_path were O(n²), 100x more segments would take ~10000x longer.
        With O(n), 100x more segments should take ~100x longer.
        We allow up to 300x to account for variance.
        """
        # Small SVG: 100 line segments
        small_segments = " ".join(f"L{i},{i}" for i in range(100))
        small_svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {small_segments}"/></svg>'

        # Large SVG: 10000 line segments (100x more)
        large_segments = " ".join(f"L{i},{i}" for i in range(10000))
        large_svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {large_segments}"/></svg>'

        # Warm up
        scourString(small_svg)
        scourString(large_svg)

        # Measure
        iterations = 3
        small_time = _time_it(lambda: scourString(small_svg), iterations)
        large_time = _time_it(lambda: scourString(large_svg), iterations)

        ratio = large_time / small_time
        # 100x more data should not take more than ~300x the time
        # (allows for constant overhead and variance)
        assert ratio < 300, (
            f"Scaling ratio {ratio:.1f}x exceeds 300x threshold. Small: {small_time:.3f}s, Large: {large_time:.3f}s"
        )


class TestLargeInput:
    """The optimizer must handle large inputs without crashing."""

    def test_very_large_path(self) -> None:
        """SVG with 50000 segments should optimize in under 10 seconds."""
        segments = " ".join(f"L{i},{i}" for i in range(50000))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {segments}"/></svg>'
        start = time.perf_counter()
        result = scourString(svg)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Took {elapsed:.1f}s — too slow for 50k segments"
        assert "<svg" in result

    def test_many_gradients(self) -> None:
        """SVG with 200 referenced gradients should optimize without timeout."""
        gradients = []
        rects = []
        for i in range(200):
            stops = "".join(
                f'<stop offset="{j / 4:.1f}" stop-color="rgb({j * 50},{255 - j * 50},0)"/>' for j in range(5)
            )
            gradients.append(f'<linearGradient id="g{i}">{stops}</linearGradient>')
            rects.append(f'<rect fill="url(#g{i})" x="{i * 5}" width="5" height="10"/>')

        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><defs>{"".join(gradients)}</defs>{"".join(rects)}</svg>'
        start = time.perf_counter()
        result = scourString(svg)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Took {elapsed:.1f}s — too slow for 200 gradients"
        assert "<svg" in result
