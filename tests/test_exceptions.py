"""Tests for the typed exception hierarchy (Sprint 1, phase S4)."""

from __future__ import annotations

import pytest

from svg_polish.exceptions import (
    InvalidOptionError,
    SvgOptimizeError,
    SvgParseError,
    SvgPathSyntaxError,
    SvgPolishError,
    SvgSecurityError,
    SvgTransformSyntaxError,
)
from svg_polish.optimizer import scour_string


class TestHierarchy:
    """Every concrete exception inherits :class:`SvgPolishError`."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            SvgParseError,
            SvgPathSyntaxError,
            SvgTransformSyntaxError,
            SvgOptimizeError,
            SvgSecurityError,
            InvalidOptionError,
        ],
    )
    def test_inherits_from_base(self, exc_cls: type[Exception]) -> None:
        assert issubclass(exc_cls, SvgPolishError)

    def test_invalid_option_is_value_error(self) -> None:
        """``InvalidOptionError`` must also satisfy ``except ValueError``."""
        assert issubclass(InvalidOptionError, ValueError)


class TestSvgParseErrorAttributes:
    """:class:`SvgParseError` carries optional source-location data."""

    def test_attributes_default_to_none(self) -> None:
        exc = SvgParseError("boom")
        assert exc.line is None
        assert exc.column is None
        assert exc.snippet is None
        assert "boom" in str(exc)

    def test_attributes_passed_via_kwargs(self) -> None:
        exc = SvgParseError("boom", line=7, column=3, snippet="<svg>")
        assert exc.line == 7
        assert exc.column == 3
        assert exc.snippet == "<svg>"

    def test_snippet_is_truncated(self) -> None:
        """Defensive truncation prevents leaking large input back to logs."""
        big = "x" * 1024
        exc = SvgParseError("boom", snippet=big)
        assert exc.snippet is not None
        assert len(exc.snippet) <= 80

    def test_chained_via_from(self) -> None:
        """``raise SvgParseError(...) from exc`` preserves the underlying cause."""
        original = ValueError("inner")
        try:
            raise SvgParseError("wrapped") from original
        except SvgParseError as exc:
            assert exc.__cause__ is original


class TestParseErrorWiredUp:
    """``scour_string`` raises the typed error on malformed input."""

    def test_unclosed_tag_raises_svg_parse_error(self) -> None:
        with pytest.raises(SvgParseError) as excinfo:
            scour_string("<svg xmlns='http://www.w3.org/2000/svg'><rect")
        assert excinfo.value.line is not None
        assert excinfo.value.column is not None

    def test_polish_error_catches_parse_error(self) -> None:
        with pytest.raises(SvgPolishError):
            scour_string("<not valid xml")
