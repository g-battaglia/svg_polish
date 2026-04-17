"""Color value conversion and shortening.

The optimizer rewrites every CSS/SVG colour expression in the document
to its shortest equivalent. Named colours (``red``, ``aliceblue``, …)
collapse to ``#hex``; ``rgb()`` and ``rgb()%`` calls become ``#hex``;
six-digit hex values with repeating pairs (``#aabbcc``) collapse to
the three-digit form (``#abc``); the result is always lowercased.

:func:`convert_color` is the value-level primitive (idempotent and
side-effect free). :func:`convert_colors` walks a DOM subtree and
applies the conversion to every fill / stroke / stop-color /
solid-color attribute *and* to the matching property inside inline
``style="…"`` declarations, returning the byte savings for
:class:`ScourStats`.
"""

from __future__ import annotations

from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.constants import _name_to_hex, rgb, rgbp
from svg_polish.style import _get_style, _set_style

__all__ = ["convert_color", "convert_colors"]


def convert_color(value: str) -> str:
    """Convert a colour value to the shortest equivalent hex representation.

    Supported input formats:

    * **Named colour** (``"red"``, ``"aliceblue"``, …) — resolved via
      :data:`svg_polish.constants._name_to_hex` (built once at import).
    * **rgb() / rgb()%** — parsed with :data:`svg_polish.constants.rgb`
      and :data:`svg_polish.constants.rgbp`. Integer values are
      converted directly; percentage values are scaled to 0-255.
    * **Hex** (``"#FF0000"``, ``"#f00"``) — six-digit hex with
      repeating pairs collapses to the three-digit form. The result is
      always lowercased.

    Inputs that match no pattern (``"url(#gradient)"``, ``"inherit"``,
    …) are returned unchanged.

    Args:
        value: A CSS/SVG colour string.

    Returns:
        The shortest equivalent hex colour string, or *value* if no
        shorter form exists.
    """
    if value in _name_to_hex:
        return _name_to_hex[value]

    s = value

    rgbpMatch = rgbp.match(s)
    if rgbpMatch is not None:
        r = int(float(rgbpMatch.group(1)) * 255.0 / 100.0)
        g = int(float(rgbpMatch.group(2)) * 255.0 / 100.0)
        b = int(float(rgbpMatch.group(3)) * 255.0 / 100.0)
        s = f"#{r:02x}{g:02x}{b:02x}"
    else:
        rgbMatch = rgb.match(s)
        if rgbMatch is not None:
            r = int(rgbMatch.group(1))
            g = int(rgbMatch.group(2))
            b = int(rgbMatch.group(3))
            s = f"#{r:02x}{g:02x}{b:02x}"

    if s[0] == "#":
        s = s.lower()
        if len(s) == 7 and s[1] == s[2] and s[3] == s[4] and s[5] == s[6]:
            s = "#" + s[1] + s[3] + s[5]

    return s


def convert_colors(element: Element) -> int:
    """Walk *element*'s subtree and shorten every colour value found.

    Iterative (explicit stack) to avoid Python's recursion overhead on
    deep documents. The set of attributes inspected per element type
    matches the SVG colour-property spec:

    * ``rect``, ``circle``, ``ellipse``, ``polygon``, ``line``,
      ``polyline``, ``path``, ``g``, ``a`` → ``fill``, ``stroke``
    * ``stop`` → ``stop-color``
    * ``solidColor`` → ``solid-color``

    Each matched attribute is rewritten via :func:`convert_color` and
    the inline ``style="…"`` declarations are inspected for the same
    property. Replacements are committed only when they strictly shorten
    the value, so the function is byte-monotonic.

    Returns:
        The number of bytes saved across the whole subtree.
    """
    numBytes = 0
    # Invariant: the stack only ever holds Element nodes — non-Element
    # children are filtered before being pushed (see loop tail), so no
    # nodeType check is needed at the top of the loop.
    stack: list[Element] = [element]

    while stack:
        node = stack.pop()

        attrsToConvert: list[str] = []
        if node.nodeName in ["rect", "circle", "ellipse", "polygon", "line", "polyline", "path", "g", "a"]:
            attrsToConvert = ["fill", "stroke"]
        elif node.nodeName in ["stop"]:
            attrsToConvert = ["stop-color"]
        elif node.nodeName in ["solidColor"]:
            attrsToConvert = ["solid-color"]

        styles = _get_style(node)
        for attr in attrsToConvert:
            oldColorValue = node.getAttribute(attr)
            if oldColorValue:
                newColorValue = convert_color(oldColorValue)
                oldBytes = len(oldColorValue)
                newBytes = len(newColorValue)
                if oldBytes > newBytes:
                    node.setAttribute(attr, newColorValue)
                    numBytes += oldBytes - len(node.getAttribute(attr))
            # The same colour properties may also appear inside a
            # style="…" declaration; rewrite there too.
            if attr in styles:
                oldColorValue = styles[attr]
                newColorValue = convert_color(oldColorValue)
                oldBytes = len(oldColorValue)
                newBytes = len(newColorValue)
                if oldBytes > newBytes:
                    styles[attr] = newColorValue
                    numBytes += oldBytes - newBytes
        _set_style(node, styles)

        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                stack.append(child)

    return numBytes
