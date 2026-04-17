"""Performance tests verifying algorithmic complexity and cache bounds.

These tests check that key operations scale as expected (e.g. O(n) not O(n²)),
that the optimizer handles large inputs without timing out, and that the
module-level :func:`functools.lru_cache` on
:func:`svg_polish.optimizer._build_url_ref_regex` stays bounded under load.

The wall-clock scaling tests are skipped under coverage instrumentation
(``pytest --cov``) because coverage tracing slows execution by 5–10× and
produces false-positive failures. The cache-bound assertions run regardless
since they are deterministic and coverage-independent.
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable

import pytest

from svg_polish.optimizer import _build_url_ref_regex, reset_caches, scour_string


def _coverage_active() -> bool:
    """Return True if ``coverage`` (or ``pytest-cov``) is currently tracing."""
    return "coverage" in sys.modules and getattr(sys, "gettrace", lambda: None)() is not None


def _time_it(func: Callable[[], object], iterations: int = 1) -> float:
    """Time a callable in seconds, summed over ``iterations`` runs."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    return time.perf_counter() - start


def _median_ratio(
    small: Callable[[], object],
    large: Callable[[], object],
    *,
    trials: int = 5,
    iterations: int = 3,
) -> tuple[float, float, float]:
    """Return (median ratio, median small time, median large time) across ``trials``.

    Median is robust against transient CI noise (a single GC pause or scheduler
    blip in either bucket would otherwise dominate the ratio). Each trial
    independently times both buckets back-to-back so they share the same
    machine state.
    """
    smalls: list[float] = []
    larges: list[float] = []
    ratios: list[float] = []
    for _ in range(trials):
        small_t = _time_it(small, iterations)
        large_t = _time_it(large, iterations)
        smalls.append(small_t)
        larges.append(large_t)
        ratios.append(large_t / small_t)
    return statistics.median(ratios), statistics.median(smalls), statistics.median(larges)


# Cache-bound tests are deterministic; only the wall-clock tests skip under coverage.
_skip_under_coverage = pytest.mark.skipif(
    _coverage_active(), reason="wall-clock thresholds are unreliable under coverage tracing"
)


@_skip_under_coverage
class TestPathScaling:
    """clean_path must scale linearly with segment count."""

    def test_clean_path_linear_time(self) -> None:
        """Path optimization scales linearly with segment count, not quadratically.

        100× more segments must take ≲ 250× longer (median over 5 trials).
        A genuine O(n²) regression would be ~10 000×, so the threshold catches
        it with > 40× margin while staying tight enough to flag a real slowdown.
        Median-of-trials absorbs single-event CI noise (GC pause, scheduler
        blip) without inflating the bound.
        """
        small_segments = " ".join(f"L{i},{i}" for i in range(100))
        small_svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {small_segments}"/></svg>'

        large_segments = " ".join(f"L{i},{i}" for i in range(10000))
        large_svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {large_segments}"/></svg>'

        scour_string(small_svg)
        scour_string(large_svg)

        ratio, small_med, large_med = _median_ratio(
            lambda: scour_string(small_svg),
            lambda: scour_string(large_svg),
            trials=5,
            iterations=3,
        )
        assert ratio < 250, (
            f"Median scaling ratio {ratio:.1f}× exceeds 250× threshold. "
            f"Median small: {small_med:.3f}s, median large: {large_med:.3f}s"
        )


@_skip_under_coverage
class TestLargeInput:
    """The optimizer must handle large inputs without crashing."""

    def test_very_large_path(self) -> None:
        """SVG with 50000 segments should optimize in under 10 seconds."""
        segments = " ".join(f"L{i},{i}" for i in range(50000))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {segments}"/></svg>'
        start = time.perf_counter()
        result = scour_string(svg)
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
        result = scour_string(svg)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Took {elapsed:.1f}s — too slow for 200 gradients"
        assert "<svg" in result


class TestUrlRefRegexCache:
    """The ``_build_url_ref_regex`` LRU cache must stay bounded under load.

    Replaces the previous unbounded ``dict`` cache, which could grow without
    limit on adversarial input with thousands of unique IDs. The bound (2048)
    is chosen to comfortably cover any realistic SVG while preventing
    pathological memory growth.
    """

    def setup_method(self) -> None:
        reset_caches()

    def test_cache_starts_empty_after_reset(self) -> None:
        info = _build_url_ref_regex.cache_info()
        assert info.currsize == 0
        assert info.hits == 0
        assert info.misses == 0

    def test_cache_size_bounded_at_2048(self) -> None:
        """Calling with 5 000 distinct IDs must not exceed the configured bound."""
        for i in range(5000):
            _build_url_ref_regex(f"unique_id_{i}")

        info = _build_url_ref_regex.cache_info()
        assert info.currsize <= 2048, f"cache grew to {info.currsize} entries (max=2048)"
        assert info.maxsize == 2048

    def test_cache_returns_same_pattern_object(self) -> None:
        """Repeated calls with the same ID return the cached compiled pattern."""
        first = _build_url_ref_regex("foo")
        second = _build_url_ref_regex("foo")
        assert first is second

    def test_cache_handles_regex_metacharacters(self) -> None:
        """IDs containing regex metacharacters are escaped before compilation."""
        # If escaping were missing, building the regex would raise re.error.
        pattern = _build_url_ref_regex("id.with+special*chars")
        assert pattern.search("url(#id.with+special*chars)") is not None
        # Confirm it does NOT match an unescaped equivalent that the metachars would otherwise hit.
        assert pattern.search("url(#idAwithBspecialCchars)") is None

    def test_reset_caches_clears_state(self) -> None:
        for i in range(10):
            _build_url_ref_regex(f"id{i}")
        assert _build_url_ref_regex.cache_info().currsize == 10
        reset_caches()
        assert _build_url_ref_regex.cache_info().currsize == 0
