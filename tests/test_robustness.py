"""Tests for robustness with edge-case SVG inputs.

Verifies that svg_polish handles unusual, extreme, and malformed inputs
gracefully — either optimizing successfully or raising meaningful errors.
"""

from __future__ import annotations

import xml.parsers.expat

import pytest

from svg_polish.optimizer import scourString

# ---------------------------------------------------------------------------
# Minimal / degenerate SVGs
# ---------------------------------------------------------------------------


class TestEmptyAndWhitespace:
    """Empty and whitespace-only SVG documents."""

    def test_empty_svg(self) -> None:
        """<svg></svg> should not crash."""
        result = scourString("<svg></svg>")
        assert "<svg" in result

    def test_svg_only_whitespace(self) -> None:
        """SVG with only whitespace text content should not crash."""
        result = scourString("<svg>   </svg>")
        assert "<svg" in result

    def test_svg_with_xml_prolog(self) -> None:
        """SVG with XML prolog should parse and output correctly."""
        svg = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        result = scourString(svg)
        assert "<svg" in result


# ---------------------------------------------------------------------------
# Malformed SVG
# ---------------------------------------------------------------------------


class TestMalformedSVG:
    """SVG that is not well-formed XML."""

    def test_malformed_svg_unclosed_tag(self) -> None:
        """Unclosed tag should raise an appropriate error."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="red"'
        with pytest.raises(xml.parsers.expat.ExpatError):
            scourString(svg)


# ---------------------------------------------------------------------------
# Elements that must be preserved
# ---------------------------------------------------------------------------


class TestPreservedElements:
    """Script and style elements must survive optimization."""

    def test_svg_with_script_preserved(self) -> None:
        """SVG with <script> element should preserve it."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<script type=\"text/javascript\">alert('hi')</script>"
            "<rect fill='red' width='10' height='10'/>"
            "</svg>"
        )
        result = scourString(svg)
        assert "<script" in result
        assert "alert" in result

    def test_svg_with_style_preserved(self) -> None:
        """SVG with <style> element should preserve the CSS content."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<style>.red { fill: red; }</style>"
            "<rect class='red' width='10' height='10'/>"
            "</svg>"
        )
        result = scourString(svg)
        assert "<style" in result
        assert "fill" in result


# ---------------------------------------------------------------------------
# Unusual content
# ---------------------------------------------------------------------------


class TestUnusualContent:
    """IDs with unicode and special characters."""

    def test_svg_with_unicode_id(self) -> None:
        """SVG with unicode characters in id should not crash."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="ünïcödé-╳" fill="red" width="10" height="10"/></svg>'
        result = scourString(svg)
        assert "<svg" in result


# ---------------------------------------------------------------------------
# Large / stress inputs
# ---------------------------------------------------------------------------


class TestStressInputs:
    """Large SVGs that stress the optimizer."""

    def test_large_path_many_segments(self) -> None:
        """SVG with 1000 line segments should optimize without crashing."""
        segments = " ".join(f"L{i},{i}" for i in range(1000))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {segments}"/></svg>'
        result = scourString(svg)
        assert "<svg" in result
        assert "<path" in result

    def test_gradient_many_stops(self) -> None:
        """SVG with 50 gradient stops should optimize without crashing."""
        stops = "".join(f'<stop offset="{i / 49:.2f}" stop-color="rgb({i},{255 - i},0)"/>' for i in range(50))
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="g1">'
            f"{stops}"
            "</linearGradient>"
            "</defs>"
            '<rect fill="url(#g1)" width="100" height="100"/>'
            "</svg>"
        )
        result = scourString(svg)
        assert "<svg" in result
        # Gradient should still be present (it's referenced)
        assert "linearGradient" in result or "g1" in result

    def test_deeply_nested_groups(self) -> None:
        """SVG with 50 levels of nested <g> elements should not crash."""
        inner = '<rect fill="red" width="10" height="10"/>'
        nested = "<g>" * 50 + inner + "</g>" * 50
        svg = f'<svg xmlns="http://www.w3.org/2000/svg">{nested}</svg>'
        result = scourString(svg)
        assert "<svg" in result
        assert "<rect" in result
