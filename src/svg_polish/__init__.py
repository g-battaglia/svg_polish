"""SVG Polish — A fast, lossless, type-safe SVG optimizer.

SVG Polish removes unnecessary data from SVG files, producing clean,
lightweight vector graphics that render identically to the originals.

Optimizations include (but are not limited to):

* Removing default attribute values and redundant style properties.
* Shortening color values (e.g. ``"#ff0000"`` → ``"red"``).
* Deduplicating gradient definitions.
* Optimizing path data (merging segments, shortening coordinates).
* Shortening or removing unused IDs.
* Stripping XML comments and editor-specific metadata.
* Simplifying transform strings.

**Lossless guarantee:** the optimized SVG is guaranteed to render identically
to the input — no visual information is lost (with the default ``decimal``
engine; see :class:`OptimizeOptions.decimal_engine`).

This project is a fork of Scour (https://github.com/scour-project/scour),
originally created by Jeff Schiller and Louis Simard.

Public API
----------

The canonical entry point is :func:`optimize` (alias of
:func:`optimize_string`). For more specialised needs:

* :func:`optimize_string` — input as ``str`` or ``bytes``, output ``str``
* :func:`optimize_bytes` — input/output as ``bytes`` (no decode round-trip)
* :func:`optimize_path` — read a file path, return optimized ``str``
* :func:`optimize_async` — coroutine wrapping :func:`optimize_string` via
  :func:`asyncio.to_thread`, suitable for use inside async web frameworks
* :func:`optimize_with_stats` — returns an :class:`OptimizeResult` with
  byte-savings, duration and per-pass counters
* :func:`optimize_file` — legacy alias of :func:`optimize_path`

Example::

    from svg_polish import optimize, OptimizeOptions

    optimized = optimize('<svg xmlns="http://www.w3.org/2000/svg">...</svg>')

    # Tighter precision and ID shortening:
    opts = OptimizeOptions(digits=3, shorten_ids=True)
    optimized = optimize(svg, opts)

    # Inspect savings:
    from svg_polish import optimize_with_stats
    result = optimize_with_stats(svg)
    print(f"saved {result.saved_bytes} bytes ({result.saved_ratio:.1%})")
"""

from __future__ import annotations

import asyncio
import optparse
import os
import time
from dataclasses import dataclass

from svg_polish.exceptions import (
    InvalidOptionError,
    SvgOptimizeError,
    SvgParseError,
    SvgPathSyntaxError,
    SvgPolishError,
    SvgSecurityError,
    SvgTransformSyntaxError,
)
from svg_polish.options import OptimizeOptions
from svg_polish.stats import ScourStats

__version__ = "1.0.0"
__all__ = [
    # Primary API.
    "optimize",
    "optimize_string",
    "optimize_bytes",
    "optimize_path",
    "optimize_file",
    "optimize_async",
    "optimize_with_stats",
    # Types.
    "OptimizeOptions",
    "OptimizeResult",
    "ScourStats",
    # Exceptions.
    "SvgPolishError",
    "SvgParseError",
    "SvgPathSyntaxError",
    "SvgTransformSyntaxError",
    "SvgOptimizeError",
    "SvgSecurityError",
    "InvalidOptionError",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class OptimizeResult:
    """Result returned by :func:`optimize_with_stats`.

    Bundles the optimized SVG together with the savings counters and timing
    information so callers can report progress without instrumenting the
    pipeline themselves.

    Attributes:
        svg: The optimized SVG document as a ``str``.
        stats: A :class:`ScourStats` instance populated by the pipeline.
        input_bytes: Size of the *input* SVG in bytes (UTF-8 encoded).
        output_bytes: Size of the *output* SVG in bytes (UTF-8 encoded).
        duration_ms: Wall-clock duration of the optimization in milliseconds.
    """

    svg: str
    stats: ScourStats
    input_bytes: int
    output_bytes: int
    duration_ms: float

    @property
    def saved_bytes(self) -> int:
        """Difference ``input_bytes - output_bytes`` (may be ``0`` or negative).

        Negative values are theoretically possible if the input was already
        more compact than the optimizer's canonical form (rare in practice).
        """
        return self.input_bytes - self.output_bytes

    @property
    def saved_ratio(self) -> float:
        """Fraction of input bytes saved, in ``[0.0, 1.0]`` for typical inputs.

        Returns ``0.0`` when :attr:`input_bytes` is zero (avoids
        :class:`ZeroDivisionError` for the empty-input edge case).
        """
        if self.input_bytes == 0:
            return 0.0
        return self.saved_bytes / self.input_bytes


def _resolve_options(options: OptimizeOptions | optparse.Values | None) -> optparse.Values | None:
    """Translate the public option types into the legacy pipeline shape.

    The internal scouring pipeline still consumes :class:`optparse.Values`
    (a holdover from the Scour era removed during Sprint 4-5
    modularization). This function lets the public API accept the canonical
    :class:`OptimizeOptions` while keeping the bridge contained to one spot.
    """
    if isinstance(options, OptimizeOptions):
        return options._to_optparse_values()
    return options


def optimize_string(
    svg_string: str | bytes,
    options: OptimizeOptions | optparse.Values | None = None,
) -> str:
    """Optimize an SVG string and return the optimized result.

    This is the canonical programmatic entry point. It accepts either a
    Unicode string or UTF-8 encoded bytes, runs the full optimization
    pipeline (namespace cleanup, style repair, color conversion, gradient
    dedup, path optimization, ID shortening, transform optimization,
    serialization), and returns the optimized SVG string.

    The optimization is **lossless** by default — the output is guaranteed
    to render identically to the input.

    Args:
        svg_string: The SVG content to optimize. Accepts ``str`` (Unicode)
            or ``bytes`` (UTF-8 encoded). Must be well-formed XML/SVG.
        options: Optional :class:`OptimizeOptions` instance. ``None`` uses
            secure-by-default settings.

    Returns:
        The optimized SVG as a ``str``.

    Raises:
        SvgParseError: If *svg_string* is not valid XML.
        SvgSecurityError: If the input violates a security policy
            (e.g. exceeds :attr:`OptimizeOptions.max_input_bytes`, or
            declares custom XML entities while
            :attr:`OptimizeOptions.allow_xml_entities` is ``False``).

    Example::

        from svg_polish import optimize_string

        result = optimize_string('<svg xmlns="http://www.w3.org/2000/svg">…</svg>')
    """
    from svg_polish.optimizer import scour_string

    return scour_string(svg_string, _resolve_options(options))


# ``optimize`` is the short, idiomatic alias kept for ergonomic use; both
# names point at the same callable so docstrings, signatures and stack
# traces stay coherent.
optimize = optimize_string


def optimize_bytes(
    svg_bytes: bytes,
    options: OptimizeOptions | optparse.Values | None = None,
) -> bytes:
    """Optimize an SVG provided as ``bytes`` and return ``bytes``.

    Convenience wrapper around :func:`optimize_string` for callers working
    end-to-end in bytes (e.g. HTTP request bodies, file contents read in
    binary mode). The output is the UTF-8 encoding of the optimized SVG.

    Args:
        svg_bytes: The SVG content as ``bytes`` (any encoding declared in
            the XML prolog is honoured by the parser).
        options: Optional :class:`OptimizeOptions` instance.

    Returns:
        The optimized SVG as UTF-8 ``bytes``.
    """
    return optimize_string(svg_bytes, options).encode("utf-8")


def optimize_path(
    path: str | os.PathLike[str],
    options: OptimizeOptions | optparse.Values | None = None,
) -> str:
    """Optimize an SVG read from *path* and return the optimized ``str``.

    Reads the file in binary mode so that the parser can honour any encoding
    declared in the XML prolog (UTF-8 by default; non-UTF-8 inputs such as
    ISO-8859-15 are handled transparently).

    Args:
        path: Filesystem path to the SVG file. Accepts ``str`` or any
            :class:`os.PathLike` (e.g. :class:`pathlib.Path`).
        options: Optional :class:`OptimizeOptions` instance.

    Returns:
        The optimized SVG as a ``str``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        SvgParseError: If the file content is not valid XML.
    """
    # Read as bytes so the parser can detect non-UTF-8 encodings from the
    # XML declaration (e.g. ISO-8859-15). ``optimize_string`` accepts both
    # ``str`` and ``bytes`` and routes bytes straight through.
    with open(path, "rb") as f:
        return optimize_string(f.read(), options)


def optimize_file(
    filename: str,
    options: OptimizeOptions | optparse.Values | None = None,
) -> str:
    """Legacy alias of :func:`optimize_path`.

    Kept so existing call sites continue to work; new code should prefer
    :func:`optimize_path`, which accepts :class:`os.PathLike` directly.
    """
    return optimize_path(filename, options)


async def optimize_async(
    svg_string: str | bytes,
    options: OptimizeOptions | optparse.Values | None = None,
) -> str:
    """Async wrapper around :func:`optimize_string`.

    Offloads the (CPU-bound) optimization to a worker thread via
    :func:`asyncio.to_thread`, so async web frameworks can call it without
    blocking the event loop. The thread-local Decimal contexts in
    :mod:`svg_polish.types` make this safe under concurrent calls.

    Args:
        svg_string: SVG content as ``str`` or ``bytes``.
        options: Optional :class:`OptimizeOptions` instance.

    Returns:
        The optimized SVG as a ``str``.
    """
    return await asyncio.to_thread(optimize_string, svg_string, options)


def optimize_with_stats(
    svg_string: str | bytes,
    options: OptimizeOptions | optparse.Values | None = None,
) -> OptimizeResult:
    """Optimize an SVG and return an :class:`OptimizeResult` with metrics.

    Same behaviour as :func:`optimize_string` but additionally captures the
    per-pass :class:`ScourStats` counters, byte sizes, and a wall-clock
    duration so callers can report compression results.

    Args:
        svg_string: SVG content as ``str`` or ``bytes``.
        options: Optional :class:`OptimizeOptions` instance.

    Returns:
        An :class:`OptimizeResult` bundling the optimized SVG, stats,
        byte counts, and duration in milliseconds.
    """
    from svg_polish.optimizer import scour_string

    stats = ScourStats()
    resolved = _resolve_options(options)
    # Compute input byte count before parsing so it reflects the on-the-wire
    # size the user actually sees. ``str`` inputs are encoded as UTF-8 to
    # match the unit used for ``output_bytes`` (which is always serialized
    # text).
    input_bytes = len(svg_string.encode("utf-8")) if isinstance(svg_string, str) else len(svg_string)
    start = time.perf_counter()
    output = scour_string(svg_string, resolved, stats=stats)
    duration_ms = (time.perf_counter() - start) * 1000.0
    return OptimizeResult(
        svg=output,
        stats=stats,
        input_bytes=input_bytes,
        output_bytes=len(output.encode("utf-8")),
        duration_ms=duration_ms,
    )
