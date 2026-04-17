"""SVG length types, unit constants, and type aliases.

Provides :class:`Unit` (integer constants and bidirectional mapping for SVG
length-unit strings), :class:`SVGLength` (parsed representation of an SVG
``<length>`` value with numeric value and unit), and common type aliases
used throughout the optimizer.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Context, Decimal
from typing import TYPE_CHECKING, Literal

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
    "DecimalEngine",
    "IdentifiedElements",
    "PathData",
    "ReferencedIDs",
    "ScouringPrecision",
    "StyleMap",
    "SVGLength",
    "TransformData",
    "Unit",
    "_precision",
    "precision_scope",
]


# Numeric engine used while parsing path / transform tokens.
# - ``"decimal"``: lossless ``Decimal`` arithmetic (default).
# - ``"float"``: native ``float``, ~3-5x faster on large path data,
#   but no longer guarantees byte-exact reproducibility. Opt-in only.
DecimalEngine = Literal["decimal", "float"]


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
# Coordinates are always ``Decimal`` under the default engine; if
# ``OptimizeOptions.decimal_engine="float"`` the inner list will hold
# ``float`` instead — the union keeps both engines type-checkable.
PathData = list[tuple[str, list[Decimal]]]

# Parsed SVG transform data: list of (transform_type, [numeric arguments]).
TransformData = list[tuple[str, list[Decimal]]]

# =============================================================================
# Scouring Precision Context
# =============================================================================


class ScouringPrecision(threading.local):
    """Thread-local Decimal contexts used for number scouring.

    SVG optimisation reduces the precision of numeric coordinates to save bytes.
    Two contexts are needed:

    * **ctx** — standard precision for most coordinates (``options.digits``).
    * **ctx_c** — tighter precision for Bézier control points
      (``options.cdigits``), which tolerate more rounding.

    **Thread safety:** inherits :class:`threading.local`, so each thread sees
    its own ``ctx`` and ``ctx_c``. The optimizer can be invoked concurrently
    from multiple threads (e.g. ``ThreadPoolExecutor``) without one thread's
    precision setting bleeding into another's output.

    Always wrap mutations in :func:`precision_scope` so the previous values
    are restored on exit — this matters when one ``scour_string`` call is
    nested inside another (e.g. when running tests in-process).

    Attributes:
        ctx: ``Context`` for standard coordinate scouring.
        ctx_c: ``Context`` for control-point scouring (usually fewer digits).
        engine: Numeric engine for path/transform parsing — ``"decimal"`` for
            lossless ``Decimal`` arithmetic (default), ``"float"`` for native
            ``float`` (faster, opt-in, lossy).
    """

    # NOTE: ``threading.local`` cannot be combined with ``__slots__`` (the
    # ``local`` C implementation already provides per-thread storage), so we
    # accept regular instance attributes here.

    ctx: Context
    ctx_c: Context
    engine: DecimalEngine

    def __init__(
        self,
        digits: int = 5,
        cdigits: int = 5,
        engine: DecimalEngine = "decimal",
    ) -> None:
        """Initialise per-thread contexts on first access.

        ``threading.local.__init__`` runs **once per thread** the first time
        the thread touches the instance, so each worker thread automatically
        gets a fresh pair of contexts at the default precision. Override the
        precision per call via :func:`precision_scope`.

        Args:
            digits: Significant-digit precision for standard coordinates.
            cdigits: Significant-digit precision for Bézier control points.
            engine: Numeric engine selector — ``"decimal"`` (lossless, default)
                or ``"float"`` (faster, opt-in, lossy).
        """
        self.ctx = Context(prec=digits)
        self.ctx_c = Context(prec=cdigits)
        self.engine = engine


# Module-level precision instance.  Set per call via :func:`precision_scope`.
# Access via ``_precision.ctx`` / ``_precision.ctx_c`` instead of raw globals.
_precision = ScouringPrecision()


@contextmanager
def precision_scope(
    digits: int,
    cdigits: int,
    engine: DecimalEngine = "decimal",
) -> Iterator[None]:
    """Bind the precision contexts and engine to *digits* / *cdigits* for the scope.

    Saves the previous values of :data:`_precision.ctx`,
    :data:`_precision.ctx_c`, and :data:`_precision.engine`, then restores
    them on exit so nested ``scour_string`` calls (e.g. in tests) cannot leak
    precision state into surrounding code.

    Intentionally does **not** touch :func:`decimal.getcontext` — the
    optimizer pipeline performs intermediate calculations at the default
    precision (28 digits) and only uses ``_precision.ctx`` / ``_precision.ctx_c``
    when explicitly rounding for output. Lowering the default context would
    break ``Decimal.quantize`` calls used during length serialisation.

    Combined with :class:`ScouringPrecision` inheriting :class:`threading.local`,
    this makes ``scour_string`` reentrant *and* thread-safe.

    Args:
        digits: Significant-digit precision for ``_precision.ctx``.
        cdigits: Significant-digit precision for ``_precision.ctx_c``.
        engine: Numeric engine — ``"decimal"`` (default, lossless) or
            ``"float"`` (faster, lossy, opt-in).

    Yields:
        ``None`` — used purely for its side effects on the precision globals.
    """
    saved_ctx = _precision.ctx
    saved_ctx_c = _precision.ctx_c
    saved_engine = _precision.engine
    _precision.ctx = Context(prec=digits)
    _precision.ctx_c = Context(prec=cdigits)
    _precision.engine = engine
    try:
        yield
    finally:
        _precision.ctx = saved_ctx
        _precision.ctx_c = saved_ctx_c
        _precision.engine = saved_engine


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
