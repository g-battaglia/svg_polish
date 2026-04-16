"""SVG Polish - A fast, lossless SVG optimizer.

SVG Polish removes unnecessary data from SVG files, producing clean,
lightweight vector graphics that render identically to the originals.

This project is a fork of Scour (https://github.com/scour-project/scour),
originally created by Jeff Schiller and Louis Simard.

Example usage::

    from svg_polish import optimize

    optimized_svg = optimize('<svg xmlns="http://www.w3.org/2000/svg">...</svg>')

"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["optimize", "optimize_file", "__version__"]


def optimize(svg_string: str | bytes, options: object | None = None) -> str:
    """Optimize an SVG string and return the optimized result.

    Args:
        svg_string: The SVG content to optimize (string or bytes).
        options: Optional configuration options. Use ``parse_args()``
            from ``svg_polish.optimizer`` for advanced configuration.

    Returns:
        The optimized SVG as a string.

    Example::

        from svg_polish import optimize

        with open("input.svg") as f:
            result = optimize(f.read())

    """
    from svg_polish.optimizer import scourString

    if isinstance(svg_string, bytes):
        svg_string = svg_string.decode("utf-8")
    return scourString(svg_string, options)


def optimize_file(filename: str, options: object | None = None) -> str:
    """Optimize an SVG file and return the optimized result.

    Args:
        filename: Path to the SVG file to optimize.
        options: Optional configuration options.

    Returns:
        The optimized SVG as a string.

    Example::

        from svg_polish import optimize_file

        result = optimize_file("input.svg")
        with open("output.svg", "w") as f:
            f.write(result)

    """
    with open(filename, encoding="utf-8") as f:
        return optimize(f.read(), options)
