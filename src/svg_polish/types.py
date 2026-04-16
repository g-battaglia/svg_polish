"""SVG length types, unit constants, and type aliases.

Provides :class:`Unit` (integer constants and bidirectional mapping for SVG
length-unit strings), :class:`SVGLength` (parsed representation of an SVG
``<length>`` value with numeric value and unit), and common type aliases
used throughout the optimizer.
"""

from __future__ import annotations

from decimal import Context, Decimal
from typing import TYPE_CHECKING

from svg_polish.constants import (
    Unit,
    number,
    sciExponent,
    scinumber,
    unit,
)

if TYPE_CHECKING:
    from xml.dom.minidom import Element

__all__ = [
    "IdentifiedElements",
    "PathData",
    "ReferencedIDs",
    "ScouringPrecision",
    "StyleMap",
    "SVGLength",
    "TransformData",
    "Unit",
    "_precision",
]


# =============================================================================
# Type Aliases
# =============================================================================

# Parsed CSS style property map: property name → value.
StyleMap = dict[str, str]

# Map of element ID → the defining Element node.
IdentifiedElements = dict[str, "Element"]

# Map of element ID → set of Elements that reference it (via url(#id)).
ReferencedIDs = dict[str, set["Element"]]

# Parsed SVG path data: list of (command_letter, [coordinate values]).
PathData = list[tuple[str, list[Decimal]]]

# Parsed SVG transform data: list of (transform_type, [numeric arguments]).
TransformData = list[tuple[str, list[Decimal]]]

# =============================================================================
# Scouring Precision Context
# =============================================================================


class ScouringPrecision:
    """Holds the two ``decimal.Context`` objects used for number scouring.

    SVG optimisation reduces the precision of numeric coordinates to save bytes.
    Two contexts are needed:

    * **ctx** — standard precision for most coordinates (``options.digits``).
    * **ctx_c** — tighter precision for Bézier control points
      (``options.cdigits``), which tolerate more rounding.

    Storing both in a single object (instead of two module-level globals)
    eliminates the ``global`` keyword, makes the precision reassignable
    from a single point, and paves the way for future reentrancy.

    Attributes:
        ctx: ``Context`` for standard coordinate scouring.
        ctx_c: ``Context`` for control-point scouring (usually fewer digits).
    """

    __slots__ = ("ctx", "ctx_c")

    def __init__(self, digits: int = 5, cdigits: int = 5) -> None:
        """Build the two ``Decimal`` contexts used by number scouring.

        Args:
            digits: Significant-digit precision for standard coordinates,
                lengths, gradient offsets, etc. Higher values preserve more
                precision but produce longer strings.
            cdigits: Significant-digit precision for Bézier control points,
                which generally tolerate more aggressive rounding than
                endpoint coordinates without visible artefacts. Defaults to
                the same value as *digits*; ``scourString`` resets this to
                ``options.cdigits`` per call.
        """
        self.ctx: Context = Context(prec=digits)
        self.ctx_c: Context = Context(prec=cdigits)


# Module-level precision instance.  Set once per ``scourString`` call.
# Access via ``_precision.ctx`` / ``_precision.ctx_c`` instead of raw globals.
_precision = ScouringPrecision()


# =============================================================================
# SVG Length Parser
# =============================================================================


class SVGLength:
    """Parsed representation of an SVG ``<length>`` value.

    An SVG length is a number optionally followed by a unit identifier.
    This class parses the string and stores the numeric :attr:`value` and
    the unit as a :class:`Unit` integer constant in :attr:`units`.

    Args:
        length_str: An SVG length string, e.g. ``"10px"``, ``"50%"``,
            ``"1.5e-2em"``, or ``"42"``.

    Attributes:
        value: The numeric portion (``int`` or ``float``).
        units: The unit as a :class:`Unit` constant (default ``Unit.NONE``).

    Raises:
        ValueError: If the string cannot be parsed (sets ``value=0``,
            ``units=Unit.INVALID``).
    """

    def __init__(self, length_str: str) -> None:
        """Parse *length_str* and set :attr:`value` / :attr:`units`.

        The fast path tries ``float(length_str)`` directly — this succeeds for
        the overwhelming majority of plain numeric values (no unit, no
        scientific notation) and avoids regex compilation. The slow path
        triggers only when the string has an exponent, a unit suffix, or both,
        and falls back to the precompiled regexes from
        :mod:`svg_polish.constants`.

        Truly invalid strings produce a "null length" (``value=0``,
        ``units=Unit.INVALID``) rather than raising — callers that need
        strictness check :attr:`units` against :attr:`Unit.INVALID`.

        Args:
            length_str: Raw SVG ``<length>`` token (e.g. ``"10px"``, ``"50%"``,
                ``"1.5e-2em"``, ``"42"``). Must not contain leading whitespace.
        """
        try:  # simple unitless and no scientific notation
            self.value = float(length_str)
            if int(self.value) == self.value:
                self.value = int(self.value)
            self.units = Unit.NONE
        except ValueError:
            # we know that the length string has an exponent, a unit, both or is invalid

            # parse out number, exponent and unit
            self.value = 0
            unitBegin = 0
            scinum = scinumber.match(length_str)
            if scinum is not None:
                # this will always match, no need to check it
                numMatch = number.match(length_str)
                assert numMatch is not None  # guaranteed by scinum match above
                expMatch = sciExponent.search(length_str, numMatch.start(0))
                assert expMatch is not None  # guaranteed by scinum match above
                self.value = float(numMatch.group(0)) * 10 ** float(expMatch.group(1))
                unitBegin = expMatch.end(1)
            else:
                # unit or invalid
                numMatch = number.match(length_str)
                if numMatch is not None:
                    self.value = float(numMatch.group(0))
                    unitBegin = numMatch.end(0)

            if int(self.value) == self.value:
                self.value = int(self.value)

            if unitBegin != 0:
                unitMatch = unit.search(length_str, unitBegin)
                if unitMatch is not None:
                    self.units = Unit.get(unitMatch.group(0))

            # invalid
            else:
                self.value = 0
                self.units = Unit.INVALID
