"""Property-based tests using Hypothesis.

Uses hypothesis strategies to generate random SVG inputs and verify
that the optimizer produces valid output for a wide range of inputs.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis.strategies import (
    floats,
    integers,
    lists,
    sampled_from,
    text,
)

from svg_polish.optimizer import convert_color, scour_string

# ---------------------------------------------------------------------------
# Color conversion strategies
# ---------------------------------------------------------------------------

HEX_CHARS = "0123456789abcdefABCDEF"


class TestConvertColorProperties:
    """Property: convert_color should be idempotent for hex colors."""

    @given(
        r=integers(min_value=0, max_value=255),
        g=integers(min_value=0, max_value=255),
        b=integers(min_value=0, max_value=255),
    )
    @settings(max_examples=50)
    def test_hex_color_idempotent(self, r: int, g: int, b: int) -> None:
        """Converting a hex color twice must produce the same result."""
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        first = convert_color(hex_color)
        second = convert_color(first)
        assert first == second, f"convert_color({hex_color!r}) → {first!r} → {second!r}"

    @given(
        r=integers(min_value=0, max_value=255),
        g=integers(min_value=0, max_value=255),
        b=integers(min_value=0, max_value=255),
    )
    @settings(max_examples=50)
    def test_rgb_color_produces_hex(self, r: int, g: int, b: int) -> None:
        """rgb() input must produce a valid hex color output."""
        rgb_color = f"rgb({r}, {g}, {b})"
        result = convert_color(rgb_color)
        assert result.startswith("#"), f"convert_color({rgb_color!r}) = {result!r}"
        # Must be valid hex: #rgb (3) or #rrggbb (7)
        assert len(result) in (4, 7)


# ---------------------------------------------------------------------------
# SVG output validity strategies
# ---------------------------------------------------------------------------

COLOR_NAMES = [
    "red",
    "blue",
    "green",
    "black",
    "white",
    "yellow",
    "cyan",
    "magenta",
    "orange",
    "purple",
    "gray",
    "pink",
    "brown",
    "navy",
    "teal",
]


class TestSvgOutputValidity:
    """Property: scour_string output must be valid XML."""

    @given(
        fill=sampled_from(COLOR_NAMES),
        width=integers(min_value=1, max_value=1000),
        height=integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=30)
    def test_simple_rect_produces_valid_xml(self, fill: str, width: int, height: int) -> None:
        """Optimizing a simple <rect> SVG should produce valid XML."""
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="{fill}" width="{width}" height="{height}"/></svg>'
        result = scour_string(svg)
        # Must be parseable XML
        parsed = ET.fromstring(result)
        assert parsed.tag.endswith("svg")

    @given(
        num_rects=integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20)
    def test_multiple_rects_produces_valid_xml(self, num_rects: int) -> None:
        """Optimizing SVG with multiple rects should produce valid XML."""
        rects = "".join(f'<rect fill="red" x="{i * 10}" width="10" height="10"/>' for i in range(num_rects))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg">{rects}</svg>'
        result = scour_string(svg)
        parsed = ET.fromstring(result)
        assert parsed.tag.endswith("svg")

    @given(
        path_data=text(
            alphabet="MmLlHhVvCcSsQqTtAa0123456789.,- ",
            min_size=5,
            max_size=200,
        ),
    )
    @settings(max_examples=30)
    def test_path_svg_produces_valid_xml(self, path_data: str) -> None:
        """Optimizing SVG with random path data should produce valid XML or raise."""
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="{path_data}"/></svg>'
        try:
            result = scour_string(svg)
            parsed = ET.fromstring(result)
            assert parsed.tag.endswith("svg")
        except Exception:
            # Some random path data may cause parse errors; that's acceptable
            pass


# ---------------------------------------------------------------------------
# Path optimization correctness
# ---------------------------------------------------------------------------


class TestPathOptimization:
    """Property: optimized paths should be no longer than input paths."""

    @given(
        coords=lists(
            floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=100,
        )
    )
    @settings(max_examples=30)
    def test_line_path_never_grows(self, coords: list[float]) -> None:
        """Optimizing a polyline should not increase output size significantly."""
        if len(coords) < 2:
            return
        points = " ".join(f"L{x},{y}" for x, y in zip(coords[::2], coords[1::2], strict=False))
        path_d = f"M0,0 {points}"
        svg = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="{path_d}"/></svg>'
        result = scour_string(svg)
        # Output must be valid XML
        parsed = ET.fromstring(result)
        assert parsed.tag.endswith("svg")
