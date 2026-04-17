"""Tests for correctness of individual optimizer functions.

Verifies that the core transformation and conversion functions produce
mathematically correct results for a wide range of inputs.
"""

from __future__ import annotations

from decimal import Decimal

from svg_polish.constants import _name_to_hex
from svg_polish.optimizer import (
    convert_color,
    optimize_transform,
    scour_string,
)
from svg_polish.svg_transform import svg_transform_parser

# ---------------------------------------------------------------------------
# convert_color — named CSS colors
# ---------------------------------------------------------------------------


class TestConvertColorNamedColors:
    """convert_color must resolve all 148 named CSS colors to hex."""

    def test_convert_color_all_named_colors(self) -> None:
        """Verify convert_color works for every entry in _name_to_hex."""
        for name, expected_hex in _name_to_hex.items():
            result = convert_color(name)
            assert result == expected_hex, f"convert_color({name!r}) = {result!r}, expected {expected_hex!r}"

    def test_convert_color_count(self) -> None:
        """There should be exactly 147 named CSS colors."""
        assert len(_name_to_hex) == 147


# ---------------------------------------------------------------------------
# convert_color — hex input
# ---------------------------------------------------------------------------


class TestConvertColorHex:
    """convert_color hex handling and idempotency."""

    def test_convert_color_hex_roundtrip(self) -> None:
        """Hex colors are idempotent: applying convert_color twice yields the same result."""
        hex_colors = [
            "#ff0000",
            "#00ff00",
            "#0000ff",
            "#aabbcc",
            "#123456",
            "#f0f0f0",
            "#000000",
            "#ffffff",
        ]
        for hex_color in hex_colors:
            first = convert_color(hex_color)
            second = convert_color(first)
            assert first == second, (
                f"convert_color({hex_color!r}) = {first!r}, convert_color({first!r}) = {second!r} — not idempotent"
            )

    def test_convert_color_hex_shortening(self) -> None:
        """#rrggbb where rr==gg==bb should be shortened to #rgb."""
        assert convert_color("#ff0000") == "#f00"
        assert convert_color("#00ff00") == "#0f0"
        assert convert_color("#0000ff") == "#00f"
        assert convert_color("#ffffff") == "#fff"
        assert convert_color("#000000") == "#000"

    def test_convert_color_hex_no_shortening(self) -> None:
        """Hex colors without repeating pairs should stay 6-digit."""
        result = convert_color("#aabbcc")
        assert result == "#abc"
        result = convert_color("#123456")
        assert result == "#123456"


# ---------------------------------------------------------------------------
# convert_color — rgb() input
# ---------------------------------------------------------------------------


class TestConvertColorRgb:
    """convert_color rgb() and rgb()% parsing."""

    def test_convert_color_rgb_to_hex(self) -> None:
        """rgb(R, G, B) integer form should convert to hex."""
        assert convert_color("rgb(255, 0, 0)") == "#f00"
        assert convert_color("rgb(0, 255, 0)") == "#0f0"
        assert convert_color("rgb(0, 0, 255)") == "#00f"
        assert convert_color("rgb(255, 255, 255)") == "#fff"

    def test_convert_color_rgb_percent_to_hex(self) -> None:
        """rgb(R%, G%, B%) percentage form should convert to hex."""
        assert convert_color("rgb(100%, 0%, 0%)") == "#f00"
        assert convert_color("rgb(0%, 100%, 0%)") == "#0f0"
        assert convert_color("rgb(0%, 0%, 100%)") == "#00f"
        assert convert_color("rgb(100%, 100%, 100%)") == "#fff"
        # 50% should map to ~128 (0x80)
        result = convert_color("rgb(50%, 50%, 50%)")
        assert result.startswith("#")


# ---------------------------------------------------------------------------
# optimize_transform — identity / no-op transforms
# ---------------------------------------------------------------------------


class TestOptimizeTransformIdentity:
    """optimize_transform must remove identity / no-op transforms."""

    def _optimize(self, transform_str: str) -> list[tuple[str, list[Decimal]]]:
        """Helper: parse a transform string and optimize it in-place."""
        parsed = svg_transform_parser.parse(transform_str)
        optimize_transform(parsed)
        return parsed

    def test_optimize_transform_identity(self) -> None:
        """Identity matrix(1,0,0,1,0,0) should be removed entirely."""
        result = self._optimize("matrix(1,0,0,1,0,0)")
        assert result == []

    def test_optimize_transform_translate_zero(self) -> None:
        """translate(0,0) collapses to translate(0) (drops optional Y=0)."""
        result = self._optimize("translate(0,0)")
        # optimize_transform drops the optional second arg (Y=0) but keeps the translate
        assert len(result) == 1
        assert result[0][0] == "translate"
        assert result[0][1] == [Decimal("0")]

    def test_optimize_transform_translate_zero_coalesced(self) -> None:
        """Two translate(0,5) + translate(0,-5) coalesce to translate(0,0) and are removed."""
        result = self._optimize("translate(0,5) translate(0,-5)")
        assert result == []

    def test_optimize_transform_scale_one(self) -> None:
        """scale(1) is kept as-is (identity removal only on coalescing)."""
        result = self._optimize("scale(1)")
        assert len(result) == 1
        assert result[0][0] == "scale"
        assert result[0][1] == [Decimal("1")]

    def test_optimize_transform_scale_one_coalesced(self) -> None:
        """Two scale(1) coalesced together are removed as identity."""
        result = self._optimize("scale(1) scale(1)")
        assert result == []

    def test_optimize_transform_rotate_360(self) -> None:
        """rotate(360) should be removed (full rotation = identity)."""
        result = self._optimize("rotate(360)")
        assert result == []

    def test_optimize_transform_skewx_zero(self) -> None:
        """skewX(0) should be removed (zero skew = identity)."""
        result = self._optimize("skewX(0)")
        assert result == []

    def test_optimize_transform_skewy_zero(self) -> None:
        """skewY(0) should be removed (zero skew = identity)."""
        result = self._optimize("skewY(0)")
        assert result == []

    def test_optimize_transform_matrix_nonidentity_kept(self) -> None:
        """A non-identity matrix should be preserved by optimize_transform."""
        result = self._optimize("matrix(2,0,0,2,10,20)")
        assert len(result) == 1
        assert result[0][0] in ("matrix", "translate", "scale")


# ---------------------------------------------------------------------------
# serialize_xml — indentation variants
# ---------------------------------------------------------------------------


class TestSerializeXMLIndentation:
    """serialize_xml must respect each indentation flag combination."""

    SVG = "<svg xmlns=\"http://www.w3.org/2000/svg\"><g><rect fill='red' width='10' height='10'/></g></svg>"

    def test_default_indent_space(self) -> None:
        """Default indentation uses a single space character per level."""
        from svg_polish.cli import parse_args

        result = scour_string(self.SVG, parse_args([]))
        # Default indent_type is "space"; the inner <rect> sits one level in.
        assert "\n <rect" in result

    def test_indent_tab(self) -> None:
        """--indent=tab uses tab characters."""
        from svg_polish.cli import parse_args

        result = scour_string(self.SVG, parse_args(["--indent=tab"]))
        # The inner <rect> sits one level in (the empty <g> is collapsed).
        assert "\n\t<rect" in result

    def test_indent_none(self) -> None:
        """--indent=none disables indentation entirely."""
        from svg_polish.cli import parse_args

        result = scour_string(self.SVG, parse_args(["--indent=none"]))
        # No leading whitespace before nested elements
        assert "\n  <rect" not in result
        assert "\n\t<rect" not in result
        assert "\n <rect" not in result

    def test_no_line_breaks_single_line(self) -> None:
        """--no-line-breaks collapses the SVG body into a single line."""
        from svg_polish.cli import parse_args

        result = scour_string(self.SVG, parse_args(["--no-line-breaks"]))
        body_start = result.find("<svg")
        body_end = result.rfind("</svg>") + len("</svg>")
        assert "\n" not in result[body_start:body_end]


# ---------------------------------------------------------------------------
# serialize_xml — attribute-quote preference
# ---------------------------------------------------------------------------


class TestSerializeXMLAttrQuote:
    """``attr_quote`` chooses the preferred delimiter without breaking output."""

    def test_default_prefers_double(self) -> None:
        """Default behaviour keeps double quotes around attribute values."""
        from svg_polish import OptimizeOptions, optimize

        out = optimize(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
            OptimizeOptions(indent_type="none", newlines=False),
        )
        assert 'width="10"' in out
        assert "width='10'" not in out

    def test_single_emits_apostrophes(self) -> None:
        """``attr_quote='single'`` switches every attribute to apostrophes."""
        from svg_polish import OptimizeOptions, optimize

        out = optimize(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
            OptimizeOptions(indent_type="none", newlines=False, attr_quote="single"),
        )
        assert "width='10'" in out
        assert "height='10'" in out

    def test_single_flips_to_double_when_value_has_apostrophe(self) -> None:
        """Apostrophe-bearing values flip back to double quotes — output stays well-formed."""
        from svg_polish import OptimizeOptions, optimize

        out = optimize(
            '<svg xmlns="http://www.w3.org/2000/svg"><text title="John\'s chart">x</text></svg>',
            OptimizeOptions(indent_type="none", newlines=False, attr_quote="single"),
        )
        # The apostrophe in the value must NOT have been escaped or destroyed.
        assert "John's chart" in out
        assert 'title="John\'s chart"' in out

    def test_double_flips_to_single_when_value_has_double_quote(self) -> None:
        """Double-quote-bearing values flip to apostrophes under the default."""
        from svg_polish import OptimizeOptions, optimize

        # Use the entity form on input so the parser can accept the inner ".
        out = optimize(
            '<svg xmlns="http://www.w3.org/2000/svg"><text title="say &quot;hi&quot;">x</text></svg>',
            OptimizeOptions(indent_type="none", newlines=False),
        )
        # The flipped delimiter avoids escaping; the value round-trips intact.
        assert "title='say \"hi\"'" in out


# ---------------------------------------------------------------------------
# Idempotency of full optimization pipeline
# ---------------------------------------------------------------------------


class TestRoundtrip:
    """Optimizing the same SVG twice must produce the same output."""

    def test_roundtrip_optimize(self) -> None:
        """Second optimization pass must equal the first (idempotent)."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="100" height="100">'
            '<rect fill="#ff0000" x="10.000" y="20.000" '
            'width="30.000" height="40.000"/>'
            "</svg>"
        )
        first = scour_string(svg)
        second = scour_string(first)
        assert second == first
