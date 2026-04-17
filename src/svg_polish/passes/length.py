"""Numeric length scouring shared by the path and transform passes.

Two value-level primitives plus a tree walker:

* :func:`scour_unitless_length` — round a single number to the
  configured precision (``digits`` for normal coordinates;
  ``cdigits`` for control points), strip trailing zeros, drop
  the leading zero of ``0.5`` → ``.5``, and emit scientific
  notation when (and only when) it strictly shortens the result.
  Pure function on a number; no DOM, no state besides
  :data:`svg_polish.types._precision`.
* :func:`scour_length` — accept a length-with-units string
  (``"12.34mm"``), peel off the unit, scour the numeric part,
  reattach the unit. Used by attribute scouring on length-typed
  attributes.
* :func:`reduce_precision` — walk an element subtree and apply
  :func:`scour_length` to every numeric style/length attribute
  (``opacity``, ``stroke-width``, ``font-size``, …) plus the
  matching CSS declaration in ``style="…"``.

Both transform and path serialisation rely on
:func:`scour_unitless_length` to normalise their numeric output, so
this module sits below them in the dependency graph (no transitive
imports of either).
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.style import _get_style, _set_style
from svg_polish.types import SVGLength, Unit, _precision

__all__ = [
    "reduce_precision",
    "scour_length",
    "scour_unitless_length",
]


def scour_length(length: str) -> str:
    """Scour a length string and reattach its unit.

    Splits *length* into ``(value, unit)`` via :class:`SVGLength`,
    rounds the value with :func:`scour_unitless_length`, then
    reattaches the unit string. Use this on attributes whose value
    may carry a unit (``stroke-width="2.5px"``); for unit-stripped
    numerics, call :func:`scour_unitless_length` directly to avoid
    the parse cost.

    Returns *length* unchanged when it isn't a real length value
    (``var(--x)``, ``calc(...)``, ``inherit``, …): emitting
    ``f"0INVALID"`` would corrupt the attribute and break later
    passes — scour 0.38.2 does exactly this and crashes downstream.
    """
    parsed = SVGLength(length)
    if parsed.units == Unit.INVALID:
        return length
    return scour_unitless_length(parsed.value) + Unit.str(parsed.units)


def scour_unitless_length(
    length: Decimal | float | str,
    renderer_workaround: bool = False,
    is_control_point: bool = False,
) -> str:
    """Round *length* to configured precision and emit the shortest text form.

    The bottom of every numeric optimisation in the library — every
    coordinate written to an SVG attribute eventually goes through
    here. Rounding picks one of two precision contexts:

    * ``_precision.ctx`` (``digits``) for normal coordinates;
    * ``_precision.ctx_c`` (``cdigits``) when *is_control_point* is
      True — Bezier control points are visually less sensitive so the
      pipeline tightens precision there to save bytes.

    Non-Decimal inputs are coerced via ``Decimal(str(length))`` (not
    ``Decimal(length)``) so a ``float`` like ``0.1`` stays ``0.1``
    instead of expanding to its true binary value.

    The output picks the shorter of the plain decimal form
    (``"0.001"`` becomes ``".001"`` after the leading-zero strip) and
    the scientific form (``"1e-3"``). Scientific is only attempted
    when the decimal form is at least 4 chars long — shorter values
    can never be beaten by scientific. *renderer_workaround* keeps
    the leading zero (``"0.5"`` stays ``"0.5"``) for renderers that
    mishandle ``.5e1``-style output.
    """
    if not isinstance(length, Decimal):
        length = getcontext().create_decimal(str(length))
    initial_length = length

    # Apply the configured precision: ``ctx.plus`` is the unary +
    # operator, which is the cheapest way to round to context.
    length = _precision.ctx_c.plus(length) if is_control_point else _precision.ctx.plus(length)

    intLength = length.to_integral_value()
    length = Decimal(intLength) if length == intLength else length.normalize()

    # Re-quantize from the original to avoid losing precision the
    # explicit ``digits`` setting was meant to preserve. Without this,
    # ``123.4`` with ``digits=2`` rounds to ``120``, not ``123``.
    nonsci = f"{length:f}"
    nonsci = f"{initial_length.quantize(Decimal(nonsci)):f}"
    if not renderer_workaround:
        if len(nonsci) > 2 and nonsci.startswith("0."):
            nonsci = nonsci[1:]
        elif len(nonsci) > 3 and nonsci.startswith("-0."):
            nonsci = "-" + nonsci[2:]
    return_value = nonsci

    # Scientific notation can only beat the plain form once the
    # mantissa+exponent overhead is amortised — under 4 chars it
    # never wins. Decimal's own ``to_sci_string`` mishandles
    # negative exponents (leaves ``0.000001`` unchanged), so we
    # build the scientific string by hand.
    if len(nonsci) > 3:
        exponent = length.adjusted()
        length = length.scaleb(-exponent).normalize()

        sci = str(length) + "e" + str(exponent)

        if len(sci) < len(nonsci):
            return_value = sci

    return return_value


def reduce_precision(element: Element) -> int:
    """Round numeric style/length attributes across the subtree to configured precision.

    For each element under *element* (depth-first, recursive) and
    each name in the length-typed attribute list (``opacity``,
    ``stroke-width``, ``font-size``, …), reads the current value
    via :class:`SVGLength`, scours it with :func:`scour_length`, and
    writes the result back when the new form is strictly shorter.
    The same loop runs over the parsed ``style="…"`` declarations.

    ``font-weight`` is intentionally absent from the list: it
    accepts enumerated values (``"normal"``, ``"bold"``, …) which
    :func:`scour_length` would corrupt.

    ``Unit.INVALID`` results (e.g. ``"inherit"``) are skipped — the
    SVG spec lets these keywords appear in length attributes and
    rounding them would drop the keyword.
    """
    num = 0

    styles = _get_style(element)
    # Length-typed inheritable properties. ``font-weight`` is
    # intentionally absent — it takes enumerated values that scour
    # would mangle.
    for lengthAttr in [
        "opacity",
        "flood-opacity",
        "fill-opacity",
        "stroke-opacity",
        "stop-opacity",
        "stroke-miterlimit",
        "stroke-dashoffset",
        "letter-spacing",
        "word-spacing",
        "kerning",
        "font-size-adjust",
        "font-size",
        "stroke-width",
    ]:
        val = element.getAttribute(lengthAttr)
        if val:
            valLen = SVGLength(val)
            # INVALID covers keyword values like "inherit"; "%" is
            # accepted because scour_length preserves the unit.
            if valLen.units != Unit.INVALID:
                newVal = scour_length(val)
                if len(newVal) < len(val):
                    num += len(val) - len(newVal)
                    element.setAttribute(lengthAttr, newVal)
        # The same property may also live inside style="…" — process
        # both forms so we don't leave one un-optimised.
        if lengthAttr in styles:
            val = styles[lengthAttr]
            valLen = SVGLength(val)
            if valLen.units != Unit.INVALID:
                newVal = scour_length(val)
                if len(newVal) < len(val):
                    num += len(val) - len(newVal)
                    styles[lengthAttr] = newVal
    _set_style(element, styles)

    for child in element.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            num += reduce_precision(child)

    return num
