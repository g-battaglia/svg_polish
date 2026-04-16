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
    number,
    sciExponent,
    scinumber,
    unit,
)

if TYPE_CHECKING:
    from xml.dom.minidom import Element


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
        self.ctx: Context = Context(prec=digits)
        self.ctx_c: Context = Context(prec=cdigits)


# Module-level precision instance.  Set once per ``scourString`` call.
# Access via ``_precision.ctx`` / ``_precision.ctx_c`` instead of raw globals.
_precision = ScouringPrecision()


# =============================================================================
# SVG Length Units
# =============================================================================


class Unit:
    """Integer constants and lookup tables for SVG length units.

    Provides bidirectional mapping between unit strings (``"px"``, ``"%"``,
    ``"em"``, etc.) and their integer constants.  Used by :class:`SVGLength`
    to parse and serialize length values.

    Attributes:
        INVALID: Sentinel value for unknown/unsupported unit strings.
        NONE: No unit (bare number).
        PCT: Percentage (``%``).
        PX: Pixels (``px``).
        PT: Points (``pt``).
        PC: Picas (``pc``).
        EM: Em (``em``).
        EX: Ex (``ex``).
        CM: Centimeters (``cm``).
        MM: Millimeters (``mm``).
        IN: Inches (``in``).
        s2u: ``dict[str, int]`` — unit string → integer constant.
        u2s: ``dict[int, str]`` — integer constant → unit string.
    """

    INVALID = -1
    NONE = 0
    PCT = 1
    PX = 2
    PT = 3
    PC = 4
    EM = 5
    EX = 6
    CM = 7
    MM = 8
    IN = 9

    # String-to-unit mapping.  Converts unit strings to their integer constants.
    s2u: dict[str, int] = {
        "": NONE,
        "%": PCT,
        "px": PX,
        "pt": PT,
        "pc": PC,
        "em": EM,
        "ex": EX,
        "cm": CM,
        "mm": MM,
        "in": IN,
    }

    # Unit-to-string mapping.  Converts unit integer constants to their strings.
    u2s: dict[int, str] = {
        NONE: "",
        PCT: "%",
        PX: "px",
        PT: "pt",
        PC: "pc",
        EM: "em",
        EX: "ex",
        CM: "cm",
        MM: "mm",
        IN: "in",
    }

    @staticmethod
    def get(unitstr: str | None) -> int:
        """Convert a unit string (e.g. ``"px"``, ``"%"``) to its integer constant.

        Returns :attr:`INVALID` for unknown strings and :attr:`NONE` for ``None``.
        """
        if unitstr is None:
            return Unit.NONE
        try:
            return Unit.s2u[unitstr]
        except KeyError:
            return Unit.INVALID

    @staticmethod
    def str(unitint: int) -> str:
        """Convert a unit integer constant to its string form.

        Returns ``"INVALID"`` for unknown constants.
        """
        try:
            return Unit.u2s[unitint]
        except KeyError:
            return "INVALID"


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
                expMatch = sciExponent.search(length_str, numMatch.start(0))
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
