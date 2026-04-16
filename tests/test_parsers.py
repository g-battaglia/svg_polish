"""Tests for the SVG path, transform, and CSS parsers.

Covers uncovered lines in svg_regex.py, svg_transform.py, and css.py.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from svg_polish.css import parseCssString
from svg_polish.svg_regex import EOF as PATH_EOF
from svg_polish.svg_regex import SVGPathParser, svg_parser
from svg_polish.svg_transform import EOF as TRANSFORM_EOF
from svg_polish.svg_transform import svg_transform_parser

# ---------------------------------------------------------------------------
# svg_regex.py — EOF repr (line 57)
# ---------------------------------------------------------------------------


class TestPathEOFRepr:
    def test_repr_returns_eof(self):
        assert repr(PATH_EOF) == "EOF"


# ---------------------------------------------------------------------------
# svg_regex.py — SyntaxError: non-command token at start (line 154)
# ---------------------------------------------------------------------------


class TestPathSyntaxErrorNonCommand:
    def test_number_at_start_raises(self):
        with pytest.raises(SyntaxError, match="expecting a command"):
            svg_parser.parse("10 20")

    def test_bare_number_raises(self):
        with pytest.raises(SyntaxError, match="expecting a command"):
            svg_parser.parse("3.14")


# ---------------------------------------------------------------------------
# svg_regex.py — rule_curveto1: T/t smooth quadratic Bezier (lines 208-214)
# ---------------------------------------------------------------------------


class TestPathCurveto1:
    def test_absolute_T_command(self):
        result = svg_parser.parse("T 10 20")
        assert len(result) == 1
        cmd, coords = result[0]
        assert cmd == "T"
        assert coords == [Decimal("10"), Decimal("20")]

    def test_relative_t_command(self):
        result = svg_parser.parse("t 5 -3")
        assert len(result) == 1
        cmd, coords = result[0]
        assert cmd == "t"
        assert coords == [Decimal("5"), Decimal("-3")]

    def test_T_multiple_pairs(self):
        result = svg_parser.parse("T 10 20 30 40")
        cmd, coords = result[0]
        assert cmd == "T"
        assert coords == [
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
            Decimal("40"),
        ]

    def test_T_as_continuation_after_Q(self):
        result = svg_parser.parse("Q 10 20 30 40 T 50 60")
        assert len(result) == 2
        assert result[0][0] == "Q"
        assert result[1][0] == "T"
        assert result[1][1] == [Decimal("50"), Decimal("60")]


# ---------------------------------------------------------------------------
# svg_regex.py — rule_elliptical_arc error branches (lines 222-262)
# ---------------------------------------------------------------------------


class TestArcErrors:
    def test_negative_rx_raises(self):
        """Line 222-223: rx < 0."""
        with pytest.raises(SyntaxError, match="nonnegative"):
            svg_parser.parse("A -1 5 0 0 0 10 10")

    def test_missing_ry_raises(self):
        """Line 226-227: non-number where ry expected."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("A 5 Z")

    def test_negative_ry_raises(self):
        """Line 229-230: ry < 0."""
        with pytest.raises(SyntaxError, match="nonnegative"):
            svg_parser.parse("A 5 -1 0 0 0 10 10")

    def test_missing_rotation_raises(self):
        """Line 233-234: non-number where rotation expected."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("A 5 5 Z")

    def test_bad_large_arc_flag_raises(self):
        """Line 238-239: large-arc-flag not 0 or 1."""
        with pytest.raises(SyntaxError, match="boolean flag"):
            svg_parser.parse("A 5 5 0 2 0 10 10")

    def test_bad_sweep_flag_raises(self):
        """Line 247-248: sweep-flag not 0 or 1."""
        with pytest.raises(SyntaxError, match="boolean flag"):
            svg_parser.parse("A 5 5 0 0 2 10 10")

    def test_missing_x_after_flags_raises(self):
        """Line 256-257: non-number where x expected after sweep flag."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("A 5 5 0 0 0 Z")

    def test_missing_y_raises(self):
        """Line 261-262: non-number where y expected."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("A 5 5 0 0 0 10 Z")


class TestArcValid:
    def test_basic_arc(self):
        result = svg_parser.parse("A 25 25 0 0 1 50 50")
        cmd, args = result[0]
        assert cmd == "A"
        assert args == [
            Decimal("25"),
            Decimal("25"),
            Decimal("0"),
            Decimal("0"),
            Decimal("1"),
            Decimal("50"),
            Decimal("50"),
        ]

    def test_relative_arc(self):
        result = svg_parser.parse("a 10 20 30 1 0 40 50")
        cmd, args = result[0]
        assert cmd == "a"
        assert len(args) == 7


# ---------------------------------------------------------------------------
# svg_regex.py — rule_coordinate SyntaxError (line 271-272)
# ---------------------------------------------------------------------------


class TestRuleCoordinateError:
    def test_non_number_token_raises(self):
        """rule_coordinate raises when token is not a number (line 271-272).

        The while-loop guard in rule_orthogonal_lineto prevents reaching this
        branch via parse(), so we call the method directly.
        """
        parser = SVGPathParser()
        token = ("command", "Z")
        with pytest.raises(SyntaxError, match="expecting a number"):
            parser.rule_coordinate(lambda: (PATH_EOF, None), token)


# ---------------------------------------------------------------------------
# svg_regex.py — rule_coordinate_pair SyntaxErrors (lines 278-283)
# ---------------------------------------------------------------------------


class TestRuleCoordinatePairErrors:
    def test_non_number_first_of_pair_raises(self):
        """Line 278-279: first token in pair is not a number."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("M 0 0 C 1 2 3 4 Z")

    def test_non_number_second_of_pair_raises(self):
        """Line 282-283: second token in pair is not a number."""
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_parser.parse("M 0 0 L 5 Z")


# ---------------------------------------------------------------------------
# svg_transform.py — EOF repr (line 29)
# ---------------------------------------------------------------------------


class TestTransformEOFRepr:
    def test_repr_returns_eof(self):
        assert repr(TRANSFORM_EOF) == "EOF"


# ---------------------------------------------------------------------------
# svg_transform.py — SyntaxError: non-command at start (line 108)
# ---------------------------------------------------------------------------


class TestTransformNonCommandStart:
    def test_number_at_start_raises(self):
        with pytest.raises(SyntaxError, match="expecting a transformation type"):
            svg_transform_parser.parse("42")

    def test_paren_at_start_raises(self):
        with pytest.raises(SyntaxError, match="expecting a transformation type"):
            svg_transform_parser.parse("(50, 50)")


# ---------------------------------------------------------------------------
# svg_transform.py — SyntaxError: missing '(' (line 113)
# ---------------------------------------------------------------------------


class TestTransformMissingOpenParen:
    def test_missing_open_paren_raises(self):
        with pytest.raises(SyntaxError, match=r"expecting '\('"):
            svg_transform_parser.parse("translate 50 50)")


# ---------------------------------------------------------------------------
# svg_transform.py — SyntaxError: missing ')' (line 116)
# ---------------------------------------------------------------------------


class TestTransformMissingCloseParen:
    def test_missing_close_paren_raises(self):
        with pytest.raises(SyntaxError, match=r"expecting '\)'"):
            svg_transform_parser.parse("translate(50 50")


# ---------------------------------------------------------------------------
# svg_transform.py — SyntaxError: non-number in rule_number (line 158)
# ---------------------------------------------------------------------------


class TestTransformRuleNumberError:
    def test_non_number_inside_parens_raises(self):
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_transform_parser.parse("translate()")

    def test_command_token_where_number_expected(self):
        with pytest.raises(SyntaxError, match="expecting a number"):
            svg_transform_parser.parse("rotate(translate)")


# ---------------------------------------------------------------------------
# css.py — parseCssString coverage (line 43 is dead code)
# ---------------------------------------------------------------------------


class TestParseCssString:
    def test_empty_string(self):
        assert parseCssString("") == []

    def test_basic_rule(self):
        result = parseCssString(".cls { fill: red; }")
        assert len(result) == 1
        assert result[0]["selector"] == ".cls"
        assert result[0]["properties"]["fill"] == "red"

    def test_no_brace_chunk_skipped(self):
        """A chunk without '{' is skipped (len(bits) != 2)."""
        result = parseCssString("no braces here")
        assert result == []

    def test_empty_properties(self):
        """An empty property block still creates a rule with no props."""
        result = parseCssString(".empty { }")
        assert len(result) == 1
        assert result[0]["properties"] == {}

    def test_multiple_rules(self):
        css = ".a { color: blue; } .b { fill: green; stroke: black; }"
        result = parseCssString(css)
        assert len(result) == 2
        assert result[0]["selector"] == ".a"
        assert result[0]["properties"]["color"] == "blue"
        assert result[1]["selector"] == ".b"
        assert result[1]["properties"]["fill"] == "green"
        assert result[1]["properties"]["stroke"] == "black"
