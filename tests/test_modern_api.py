"""Tests for the modern public API surface (Sprint 3, M3).

Covers the canonical entry points (:func:`optimize`, :func:`optimize_string`,
:func:`optimize_bytes`, :func:`optimize_path`, :func:`optimize_async`,
:func:`optimize_with_stats`), the :class:`OptimizeResult` dataclass, and
the :class:`ScourStats` dataclass refactor.
"""

from __future__ import annotations

import asyncio
import dataclasses
import pathlib
from typing import Any

import pytest

from svg_polish import (
    OptimizeOptions,
    OptimizeResult,
    ScourStats,
    optimize,
    optimize_async,
    optimize_bytes,
    optimize_file,
    optimize_path,
    optimize_string,
    optimize_with_stats,
)

# A non-trivial input so the optimizer has something to actually shrink:
# colour shortening, redundant attributes, default values, and the prolog
# all contribute to a measurable byte saving.
SAMPLE_SVG = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">'
    '  <rect x="0.0000" y="0.000" width="100" height="100" '
    '  fill="#ff0000" stroke-width="1"/>'
    "</svg>"
)


class TestOptimizeAlias:
    """``optimize`` must be the canonical alias of ``optimize_string``."""

    def test_optimize_is_optimize_string(self) -> None:
        # Both names share the same callable so docstrings, signatures and
        # stack traces stay coherent (no double-indirect wrapper).
        assert optimize is optimize_string

    def test_optimize_string_accepts_str(self) -> None:
        result = optimize_string(SAMPLE_SVG)
        assert "<svg" in result
        assert isinstance(result, str)

    def test_optimize_string_accepts_bytes(self) -> None:
        result = optimize_string(SAMPLE_SVG.encode("utf-8"))
        assert "<svg" in result
        assert isinstance(result, str)


class TestOptimizeBytes:
    """``optimize_bytes`` round-trips through bytes for HTTP-style callers."""

    def test_returns_bytes(self) -> None:
        result = optimize_bytes(SAMPLE_SVG.encode("utf-8"))
        assert isinstance(result, bytes)
        assert b"<svg" in result

    def test_output_is_utf8(self) -> None:
        # The output must be decodable as UTF-8 so callers can treat it as
        # a payload regardless of the original input encoding.
        result = optimize_bytes(SAMPLE_SVG.encode("utf-8"))
        assert result.decode("utf-8")


class TestOptimizePath:
    """``optimize_path`` accepts both ``str`` and :class:`pathlib.Path`."""

    def test_accepts_str_path(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "in.svg"
        f.write_text(SAMPLE_SVG)
        result = optimize_path(str(f))
        assert "<svg" in result

    def test_accepts_pathlib(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "in.svg"
        f.write_text(SAMPLE_SVG)
        result = optimize_path(f)
        assert "<svg" in result

    def test_missing_file_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            optimize_path(tmp_path / "does-not-exist.svg")

    def test_optimize_file_alias(self, tmp_path: pathlib.Path) -> None:
        # ``optimize_file`` is preserved as a back-compat alias of
        # ``optimize_path``; both should produce the same output.
        f = tmp_path / "in.svg"
        f.write_text(SAMPLE_SVG)
        assert optimize_file(str(f)) == optimize_path(f)


class TestOptimizeAsync:
    """``optimize_async`` defers to a thread but returns the same result."""

    def test_returns_string(self) -> None:
        result = asyncio.run(optimize_async(SAMPLE_SVG))
        assert "<svg" in result
        assert isinstance(result, str)

    def test_matches_sync_output(self) -> None:
        # Async wrapper must produce byte-identical output to the sync call;
        # difference would mean state leak through ``asyncio.to_thread``.
        sync = optimize_string(SAMPLE_SVG)
        async_ = asyncio.run(optimize_async(SAMPLE_SVG))
        assert sync == async_


class TestOptimizeWithStats:
    """``optimize_with_stats`` returns a populated :class:`OptimizeResult`."""

    def test_returns_optimize_result(self) -> None:
        result = optimize_with_stats(SAMPLE_SVG)
        assert isinstance(result, OptimizeResult)
        assert isinstance(result.stats, ScourStats)

    def test_input_and_output_bytes_set(self) -> None:
        result = optimize_with_stats(SAMPLE_SVG)
        assert result.input_bytes == len(SAMPLE_SVG.encode("utf-8"))
        assert result.output_bytes == len(result.svg.encode("utf-8"))

    def test_saved_bytes_positive_for_redundant_input(self) -> None:
        # SAMPLE_SVG contains compressible cruft (#ff0000 → red, leading
        # zeros, default stroke-width) so the optimizer must save bytes.
        result = optimize_with_stats(SAMPLE_SVG)
        assert result.saved_bytes > 0

    def test_saved_ratio_in_unit_interval(self) -> None:
        result = optimize_with_stats(SAMPLE_SVG)
        assert 0.0 <= result.saved_ratio <= 1.0

    def test_duration_ms_positive(self) -> None:
        result = optimize_with_stats(SAMPLE_SVG)
        assert result.duration_ms > 0.0

    def test_passes_options_through(self) -> None:
        # Strip the prolog via OptimizeOptions and verify the wrapper
        # honours it — proves the bridge to the legacy pipeline still works.
        result = optimize_with_stats(
            SAMPLE_SVG,
            OptimizeOptions(strip_xml_prolog=True),
        )
        assert not result.svg.startswith("<?xml")

    def test_stats_counters_populated(self) -> None:
        # The optimizer should at minimum repair the redundant
        # ``stroke-width="1"`` (default) or the verbose ``#ff0000`` colour,
        # so the relevant counters must be non-zero.
        result = optimize_with_stats(SAMPLE_SVG)
        assert result.stats.num_attributes_removed > 0 or result.stats.num_bytes_saved_in_colors > 0

    def test_empty_input_does_not_divide_by_zero(self) -> None:
        # OptimizeResult.saved_ratio guards against ZeroDivisionError when
        # input_bytes is zero. Construct the dataclass directly so we test
        # the property in isolation.
        empty = OptimizeResult(svg="", stats=ScourStats(), input_bytes=0, output_bytes=0, duration_ms=0.0)
        assert empty.saved_ratio == 0.0


class TestOptimizeResult:
    """:class:`OptimizeResult` immutability and properties."""

    def test_is_frozen(self) -> None:
        result = optimize_with_stats(SAMPLE_SVG)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.svg = "tampered"  # type: ignore[misc]

    def test_saved_bytes_property(self) -> None:
        r = OptimizeResult(svg="x", stats=ScourStats(), input_bytes=100, output_bytes=70, duration_ms=1.0)
        assert r.saved_bytes == 30
        assert r.saved_ratio == 0.3


class TestScourStatsDataclass:
    """:class:`ScourStats` was migrated to ``@dataclass(slots=True)``."""

    def test_default_zero(self) -> None:
        stats = ScourStats()
        assert stats.num_elements_removed == 0
        assert stats.num_bytes_saved_in_path_data == 0

    def test_total_bytes_saved_sum(self) -> None:
        stats = ScourStats(
            num_bytes_saved_in_colors=1,
            num_bytes_saved_in_path_data=2,
            num_bytes_saved_in_comments=4,
            num_bytes_saved_in_ids=8,
            num_bytes_saved_in_lengths=16,
            num_bytes_saved_in_transforms=32,
        )
        assert stats.total_bytes_saved == 63

    def test_reset_zeroes_every_field(self) -> None:
        stats = ScourStats(num_elements_removed=10, num_bytes_saved_in_colors=5)
        stats.reset()
        assert stats.num_elements_removed == 0
        assert stats.num_bytes_saved_in_colors == 0

    def test_repr_lists_nonzero_values(self) -> None:
        # Dataclass-generated ``__repr__`` should include the populated
        # fields so logs are useful out of the box.
        stats = ScourStats(num_elements_removed=3)
        assert "num_elements_removed=3" in repr(stats)

    def test_uses_slots(self) -> None:
        # ``slots=True`` means there's no ``__dict__``; touching
        # an undeclared attribute must raise ``AttributeError``.
        stats: Any = ScourStats()
        with pytest.raises(AttributeError):
            stats.totally_made_up_field = 1
