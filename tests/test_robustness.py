"""Tests for robustness with edge-case SVG inputs.

Verifies that svg_polish handles unusual, extreme, and malformed inputs
gracefully — either optimizing successfully or raising meaningful errors.
"""

from __future__ import annotations

import pytest

from svg_polish.exceptions import SvgParseError
from svg_polish.optimizer import scour_string

# ---------------------------------------------------------------------------
# Minimal / degenerate SVGs
# ---------------------------------------------------------------------------


class TestEmptyAndWhitespace:
    """Empty and whitespace-only SVG documents."""

    def test_empty_svg(self) -> None:
        """<svg></svg> should not crash."""
        result = scour_string("<svg></svg>")
        assert "<svg" in result

    def test_svg_only_whitespace(self) -> None:
        """SVG with only whitespace text content should not crash."""
        result = scour_string("<svg>   </svg>")
        assert "<svg" in result

    def test_svg_with_xml_prolog(self) -> None:
        """SVG with XML prolog should parse and output correctly."""
        svg = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        result = scour_string(svg)
        assert "<svg" in result


# ---------------------------------------------------------------------------
# Malformed SVG
# ---------------------------------------------------------------------------


class TestMalformedSVG:
    """SVG that is not well-formed XML."""

    def test_malformed_svg_unclosed_tag(self) -> None:
        """Unclosed tag should raise an appropriate error."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="red"'
        with pytest.raises(SvgParseError) as excinfo:
            scour_string(svg)
        # SvgParseError carries source-location data when the parser exposes it.
        assert excinfo.value.line is not None
        assert excinfo.value.column is not None


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
        result = scour_string(svg)
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
        result = scour_string(svg)
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
        result = scour_string(svg)
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
        result = scour_string(svg)
        assert "<svg" in result
        assert "<path" in result

    def test_gradient_many_stops(self) -> None:
        """SVG with 200 gradient stops should optimize without crashing."""
        stops = "".join(
            f'<stop offset="{i / 199:.4f}" stop-color="rgb({i % 256},{(255 - i) % 256},0)"/>' for i in range(200)
        )
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
        result = scour_string(svg)
        assert "<svg" in result
        # Gradient should still be present (it's referenced)
        assert "linearGradient" in result or "g1" in result

    def test_svg_over_one_megabyte(self) -> None:
        """SVG larger than 1 MB should optimize without exhausting memory."""
        segments = " ".join(f"L{i},{i}" for i in range(150_000))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 {segments}"/></svg>'
        # Sanity check the input is actually >1 MB
        assert len(svg) > 1_048_576
        result = scour_string(svg)
        assert "<svg" in result
        assert "<path" in result

    def test_deeply_nested_groups(self) -> None:
        """SVG with 50 levels of nested <g> elements should not crash."""
        inner = '<rect fill="red" width="10" height="10"/>'
        nested = "<g>" * 50 + inner + "</g>" * 50
        svg = f'<svg xmlns="http://www.w3.org/2000/svg">{nested}</svg>'
        result = scour_string(svg)
        assert "<svg" in result
        assert "<rect" in result


# ---------------------------------------------------------------------------
# Non-numeric style values (CSS var(), calc(), keywords)
# ---------------------------------------------------------------------------


class TestNonNumericStyleValues:
    """``repair_style`` must not crash on CSS values that aren't plain floats.

    Real-world SVGs frequently embed ``style="fill-opacity: var(--x, 0.5)"``
    and similar CSS-only constructs. Scour 0.38.2 raises ``ValueError``
    here; svg_polish leaves the property untouched and continues.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "var(--my-opacity, 0.5)",
            "var(--my-opacity)",
            "calc(1 - 0.5)",
            "inherit",
            "currentColor",
        ],
    )
    def test_fill_opacity_non_numeric_does_not_crash(self, value: str) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<rect width="10" height="10" style="fill: red; fill-opacity: {value}"/>'
            "</svg>"
        )
        result = scour_string(svg)
        assert value in result, f"value {value!r} must be preserved verbatim"
        assert 'fill="red"' in result or "fill: red" in result or "fill:red" in result

    @pytest.mark.parametrize("value", ["var(--x, 0.5)", "calc(0.5)", "inherit"])
    def test_stroke_opacity_non_numeric_does_not_crash(self, value: str) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<rect width="10" height="10" style="stroke: blue; stroke-opacity: {value}"/>'
            "</svg>"
        )
        result = scour_string(svg)
        assert value in result

    @pytest.mark.parametrize("value", ["var(--x, 0.5)", "calc(0.5)", "inherit"])
    def test_opacity_non_numeric_does_not_crash(self, value: str) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<rect width="10" height="10" style="fill: red; opacity: {value}"/>'
            "</svg>"
        )
        result = scour_string(svg)
        assert value in result
        # opacity != 0 ⇒ fill must NOT be stripped
        assert "fill" in result

    @pytest.mark.parametrize("value", ["var(--w, 2)", "calc(1 + 1)", "inherit"])
    def test_stroke_width_non_numeric_does_not_crash(self, value: str) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<rect width="10" height="10" style="stroke: blue; stroke-width: {value}"/>'
            "</svg>"
        )
        result = scour_string(svg)
        assert value in result
        # stroke-width is unparseable ⇒ stroke must NOT be stripped
        assert "stroke" in result


# ---------------------------------------------------------------------------
# Non-numeric values in transform / path / length attributes
# ---------------------------------------------------------------------------


class TestNonNumericTransformValues:
    """``optimize_transforms`` must not crash on transforms holding CSS tokens.

    Some toolchains emit ``transform="translate(var(--x), 0)"`` so the
    parser sees an identifier where it expects a number. svg_polish leaves
    the attribute untouched; scour 0.38.2 raises ``SyntaxError``.
    """

    @pytest.mark.parametrize(
        "transform",
        [
            "translate(var(--x), 0)",
            "rotate(calc(45deg))",
            "scale(var(--scale, 1))",
        ],
    )
    def test_transform_with_var_calc_does_not_crash(self, transform: str) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<rect transform="{transform}" width="10" height="10" fill="red"/>'
            "</svg>"
        )
        result = scour_string(svg)
        assert transform in result, f"transform {transform!r} must be preserved verbatim"


class TestNonNumericPathData:
    """``clean_path`` must not crash on ``d`` attributes that aren't real paths.

    Real SVGs sometimes carry placeholder or templated ``d`` data such as
    ``"M 0 0 L var(--x) 10 Z"`` or ``"   "``. The parser raises
    ``SyntaxError``/``IndexError``; the pass leaves the attribute untouched.
    """

    @pytest.mark.parametrize(
        "d",
        [
            "M 0 0 L var(--x) 10 Z",
            "M 0 0 L calc(10 + 5) 10 Z",
        ],
    )
    def test_path_with_var_calc_does_not_crash(self, d: str) -> None:
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="{d}" fill="red"/></svg>'
        result = scour_string(svg)
        assert d in result, f"d={d!r} must be preserved verbatim"

    @pytest.mark.parametrize("d", ["", "   ", "\t\n"])
    def test_empty_or_whitespace_path_does_not_crash(self, d: str) -> None:
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="{d}" fill="red"/></svg>'
        # Must not raise; empty d may be dropped, but no crash either way.
        scour_string(svg)


class TestScourLengthInvalid:
    """``scour_length`` must return the input verbatim for non-length values.

    ``SVGLength`` returns ``Unit.INVALID`` for tokens like ``"inherit"`` or
    ``"var(--w)"``. Without the guard, ``scour_length`` would emit
    ``"0INVALID"`` and corrupt the attribute downstream.
    """

    def test_scour_length_returns_input_for_var(self) -> None:
        from svg_polish.passes.length import scour_length

        assert scour_length("var(--w)") == "var(--w)"

    def test_scour_length_returns_input_for_keyword(self) -> None:
        from svg_polish.passes.length import scour_length

        assert scour_length("inherit") == "inherit"

    def test_scour_length_normalises_real_length(self) -> None:
        from svg_polish.passes.length import scour_length

        # Sanity: real lengths still round-trip through the optimiser.
        assert scour_length("12.500px") == "12.5px"


class TestSVGLengthSlowPathUnits:
    """``SVGLength`` must always set ``units``, even when the unit token misses.

    Inputs like ``"10e"`` parse the number but fail the unit regex; without
    the fallback, ``units`` would be undefined and any ``length.units`` access
    downstream would raise ``AttributeError``.
    """

    @pytest.mark.parametrize("value", ["10e", "5xyz", "0INVALID"])
    def test_unparseable_unit_yields_invalid(self, value: str) -> None:
        from svg_polish.types import SVGLength, Unit

        parsed = SVGLength(value)
        assert parsed.units == Unit.INVALID
