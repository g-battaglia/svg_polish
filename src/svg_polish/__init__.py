"""SVG Polish — A fast, lossless SVG optimizer.

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
to the input — no visual information is lost.

This project is a fork of Scour (https://github.com/scour-project/scour),
originally created by Jeff Schiller and Louis Simard.

Public API
----------

.. autofunction:: optimize
.. autofunction:: optimize_file

Example usage::

    from svg_polish import optimize

    optimized_svg = optimize('<svg xmlns="http://www.w3.org/2000/svg">...</svg>')

For file-level operations::

    from svg_polish import optimize_file

    result = optimize_file("input.svg")
    with open("output.svg", "w") as f:
        f.write(result)

For advanced configuration, see :func:`svg_polish.optimizer.parse_args`.
"""

from __future__ import annotations

import optparse

__version__ = "1.0.0"
__all__ = ["optimize", "optimize_file", "__version__"]


def optimize(svg_string: str | bytes, options: optparse.Values | None = None) -> str:
    """Optimize an SVG string and return the optimized result.

    This is the primary entry point for programmatic SVG optimization.
    It accepts either a Unicode string or UTF-8 encoded bytes, runs the
    full optimization pipeline (namespace cleanup, style repair, color
    conversion, gradient dedup, path optimization, ID shortening, transform
    optimization, serialization), and returns the optimized SVG string.

    The optimization is **lossless** — the output is guaranteed to render
    identically to the input.

    Args:
        svg_string: The SVG content to optimize.  Accepts ``str`` (Unicode)
            or ``bytes`` (UTF-8 encoded).  Must be well-formed XML/SVG.
        options: Optional configuration object (as returned by
            :func:`~svg_polish.optimizer.parse_args`).  Pass ``None`` to use
            sensible defaults (good compression, safe behavior).

    Returns:
        The optimized SVG as a string.

    Raises:
        xml.parsers.expat.ExpatError: If *svg_string* is not valid XML.

    Example::

        from svg_polish import optimize

        with open("input.svg") as f:
            result = optimize(f.read())

        # With bytes input:
        result = optimize(b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#ff0000"/></svg>')

    """
    from svg_polish.optimizer import scourString

    # Pass bytes straight through: scourString lets xml.dom.minidom detect the
    # encoding from the XML declaration, which handles non-UTF-8 files.
    return scourString(svg_string, options)


def optimize_file(filename: str, options: optparse.Values | None = None) -> str:
    """Optimize an SVG file and return the optimized result.

    Convenience wrapper around :func:`optimize` that reads the file and
    passes its contents to the optimizer.  The file is opened in text mode
    with UTF-8 decoding — this covers the vast majority of SVG inputs. For
    files declaring a non-UTF-8 encoding in their XML prolog (e.g.
    ISO-8859-15), call :func:`svg_polish.optimizer.scourXmlFile` directly,
    which reads the file as bytes and lets ``xml.dom.minidom`` detect the
    encoding from the prolog.

    Args:
        filename: Path to the SVG file to optimize.
        options: Optional configuration object (as returned by
            :func:`~svg_polish.optimizer.parse_args`).  Pass ``None`` for
            sensible defaults.

    Returns:
        The optimized SVG as a string.

    Raises:
        FileNotFoundError: If *filename* does not exist.
        UnicodeDecodeError: If the file is not valid UTF-8 (use
            :func:`svg_polish.optimizer.scourXmlFile` for non-UTF-8 inputs).
        xml.parsers.expat.ExpatError: If the file content is not valid XML.

    Example::

        from svg_polish import optimize_file

        result = optimize_file("input.svg")
        with open("output.svg", "w") as f:
            f.write(result)

    """
    # Use ``with`` so the handle closes even if optimize() raises mid-parse.
    with open(filename, encoding="utf-8") as f:
        return optimize(f.read(), options)
