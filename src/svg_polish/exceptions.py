"""Typed exception hierarchy for ``svg_polish``.

All errors raised by the public API derive from :class:`SvgPolishError`, so a
consumer can write a single broad ``except SvgPolishError`` and still discriminate
specific failure modes via subclasses.

Hierarchy::

    SvgPolishError                              (base — never raised directly)
    ├── SvgParseError                           (malformed XML; carries line/column/snippet)
    ├── SvgPathSyntaxError                      (malformed ``d`` attribute)
    ├── SvgTransformSyntaxError                 (malformed ``transform`` attribute)
    ├── SvgOptimizeError                        (unrecoverable error inside an optimization pass)
    ├── SvgSecurityError                        (input rejected by the secure-by-default checks)
    └── InvalidOptionError (also ValueError)    (invalid value passed to ``OptimizeOptions``)

The ``Svg*Error`` prefix is canonical: every public exception starts with
``Svg`` so users searching the library namespace can find them grouped together.
"""

from __future__ import annotations


class SvgPolishError(Exception):
    """Root of the ``svg_polish`` exception hierarchy.

    Never raised on its own — present only so that callers can write
    ``except SvgPolishError`` and catch every library-specific failure with a
    single clause.
    """


class SvgParseError(SvgPolishError):
    """Raised when the input cannot be parsed as well-formed XML/SVG.

    The optional :attr:`line`, :attr:`column`, and :attr:`snippet` attributes
    locate the failure when the underlying parser exposes that information.
    They are intentionally kept as plain attributes (no positional args) so
    that ``str(exc)`` stays a clean human-readable message and machine-readable
    location data remains accessible.

    The :attr:`snippet` is **deliberately short** (≤ 80 chars) and never
    includes user-supplied stack frames — this avoids leaking large chunks of
    untrusted input back to logs or callers.
    """

    line: int | None
    column: int | None
    snippet: str | None

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.line = line
        self.column = column
        # Defensive truncation: never echo more than 80 chars of input back.
        self.snippet = snippet[:80] if snippet else None


class SvgPathSyntaxError(SvgPolishError):
    """Raised when a ``<path d="...">`` value violates the SVG path grammar."""


class SvgTransformSyntaxError(SvgPolishError):
    """Raised when a ``transform="..."`` value violates the SVG transform grammar."""


class SvgOptimizeError(SvgPolishError):
    """Raised when an optimization pass hits an unrecoverable internal error.

    Used to wrap unexpected failures inside the pipeline (broken DOM state,
    invariant violations) so they surface as :class:`SvgPolishError` rather
    than as bare ``RuntimeError``/``AssertionError``.
    """


class SvgSecurityError(SvgPolishError):
    """Raised when input is rejected by the secure-by-default checks.

    Triggered by:

    * Input larger than ``OptimizeOptions.max_input_bytes`` (default 100 MB).
    * XML entities / DOCTYPE definitions in the input when
      ``OptimizeOptions.allow_xml_entities`` is ``False`` (default), e.g.
      billion-laughs or XXE payloads.

    The exception message is deliberately generic so it does not leak input
    fragments back into logs.
    """


class InvalidOptionError(SvgPolishError, ValueError):
    """Raised when an :class:`~svg_polish.options.OptimizeOptions` value is invalid.

    Subclasses :class:`ValueError` as well, so call sites that want the
    standard "bad input" semantics can still write ``except ValueError``.
    """


__all__ = [
    "SvgPolishError",
    "SvgParseError",
    "SvgPathSyntaxError",
    "SvgTransformSyntaxError",
    "SvgOptimizeError",
    "SvgSecurityError",
    "InvalidOptionError",
]
