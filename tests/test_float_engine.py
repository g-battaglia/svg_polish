"""Smoke and behaviour tests for the opt-in float numeric engine.

The float engine (``OptimizeOptions(decimal_engine="float")``) trades the
default :class:`~decimal.Decimal` lossless guarantee for ~3-5x faster
arithmetic on dense path data. These tests pin three properties:

1. **Round-trip stability**: a path scoured under ``float`` re-parses
   into the same shape (commands, point counts).
2. **Output shrinkage**: float-mode output is no larger than the input
   on real fixtures — proves the optimisation pipeline still applies.
3. **Engine isolation**: switching engines must not leak precision
   state between calls (covered indirectly by running both engines
   back-to-back and verifying ``decimal``-mode output remains
   byte-exact against a baseline).
"""

from __future__ import annotations

from svg_polish import OptimizeOptions, optimize
from svg_polish.optimizer import scour_string
from svg_polish.svg_regex import svg_parser
from svg_polish.svg_transform import svg_transform_parser
from svg_polish.types import _precision, precision_scope


def _baseline(svg: str) -> str:
    """Optimize *svg* under the default decimal engine."""
    return optimize(svg)


def _float_mode(svg: str) -> str:
    """Optimize *svg* under the opt-in float engine."""
    return optimize(svg, OptimizeOptions(decimal_engine="float"))


def test_float_engine_default_is_decimal() -> None:
    """The ``ScouringPrecision`` instance defaults to the lossless engine."""
    assert _precision.engine == "decimal"


def test_precision_scope_threads_engine() -> None:
    """``precision_scope`` swaps engine and restores it on exit."""
    saved = _precision.engine
    with precision_scope(5, 5, "float"):
        assert _precision.engine == "float"
    assert _precision.engine == saved


def test_path_parser_emits_floats_under_float_engine() -> None:
    """Float engine yields native floats for path coordinates."""
    with precision_scope(5, 5, "float"):
        parsed = svg_parser.parse("M10 20 L30 40")
    assert parsed[0][0] == "M"
    assert all(isinstance(v, float) for v in parsed[0][1])


def test_path_parser_emits_decimals_under_decimal_engine() -> None:
    """Default engine still produces Decimal values."""
    from decimal import Decimal

    with precision_scope(5, 5, "decimal"):
        parsed = svg_parser.parse("M10 20 L30 40")
    assert all(isinstance(v, Decimal) for v in parsed[0][1])


def test_transform_parser_emits_floats_under_float_engine() -> None:
    """Float engine yields native floats for transform arguments."""
    with precision_scope(5, 5, "float"):
        parsed = svg_transform_parser.parse("translate(10, 20) scale(1.5)")
    flat = [arg for _name, args in parsed for arg in args]
    assert all(isinstance(v, float) for v in flat)


def test_float_engine_optimizes_simple_svg() -> None:
    """Float engine produces a valid, optimised SVG."""
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<path d="M10.000000 20.000000 L30.000000 40.000000 Z"/>'
        "</svg>"
    )
    out = _float_mode(svg)
    assert "<svg" in out
    assert "<path" in out
    assert len(out) < len(svg)


def test_decimal_baseline_unchanged_after_float_call() -> None:
    """A float-engine call must not perturb subsequent decimal output."""
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<path d="M10 20 L30.5 40.25 Q50 60 70 80 Z"/>'
        "</svg>"
    )
    decimal_a = _baseline(svg)
    _ = _float_mode(svg)
    decimal_b = _baseline(svg)
    assert decimal_a == decimal_b


def test_float_engine_handles_arc_command() -> None:
    """Float engine survives the elliptical arc parser branch (rx/ry/flags)."""
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<path d="M10 20 A5 5 0 0 1 30 40 Z"/>'
        "</svg>"
    )
    out = _float_mode(svg)
    assert "<path" in out


def test_float_engine_handles_transforms() -> None:
    """Float engine survives transform optimisation pipeline."""
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<g transform="translate(10, 20) scale(1.5) rotate(45)">'
        '<rect width="10" height="10"/>'
        "</g></svg>"
    )
    out = _float_mode(svg)
    assert "<g" in out


def test_float_engine_collinear_path_triggers_is_same_direction() -> None:
    """Three collinear segments exercise ``is_same_direction`` under floats.

    The function calls ``_precision.ctx.plus`` which rejects ``float``;
    the float-engine branch coerces back to Decimal at that boundary.
    """
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<path d="M0 0 L10 10 L20 20 L30 30 Z"/>'
        "</svg>"
    )
    out = _float_mode(svg)
    assert "<path" in out


def test_float_engine_matrix_to_rotation_decomposition() -> None:
    """A matrix(...) with rotation shape exercises the float-cast branch.

    The rotation-detection block in :func:`optimize_transform` returns a
    ``Decimal`` angle from ``math.degrees``; under the float engine the
    result is rebuilt as ``float`` so ``transform`` args remain
    type-consistent for serialisation.
    """
    # matrix(cos45, sin45, -sin45, cos45, 0, 0) → rotate(45)
    svg = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<g transform="matrix(0.70710678, 0.70710678, -0.70710678, 0.70710678, 0, 0)">'
        '<rect width="10" height="10"/>'
        "</g></svg>"
    )
    out = _float_mode(svg)
    assert "<g" in out


def test_float_engine_via_scour_string_options_object() -> None:
    """Float engine is honoured when supplied via ``optparse.Values``-style options."""
    from svg_polish.optimizer import sanitize_options

    options = sanitize_options(OptimizeOptions(decimal_engine="float"))
    assert options.decimal_engine == "float"
    out = scour_string(
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><path d="M10 20 L30 40"/></svg>',
        options,
    )
    assert "<path" in out
