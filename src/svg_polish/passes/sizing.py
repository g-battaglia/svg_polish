"""Convert ``<svg width=… height=…>`` into the more compact ``viewBox=…``.

When ``--enable-viewboxing`` is requested, this pass tries to drop
the explicit ``width`` / ``height`` attributes from the document
element and replace them with an equivalent ``viewBox``. The result
is a document that scales naturally with its container instead of
being pinned to a fixed pixel size.

The conversion is a no-op when:

* the document already has a ``viewBox`` whose origin isn't ``(0,0)``
  or whose size doesn't match the explicit ``width`` / ``height``
  (overwriting would change rendering);
* the explicit ``width`` / ``height`` use a non-pixel unit
  (``cm``, ``in``, …) and ``--renderer-workaround`` is on — librsvg
  in particular gets the rendering wrong when these are dropped in
  favour of a unitless ``viewBox``.
"""

from __future__ import annotations

import optparse
from xml.dom.minidom import Element

from svg_polish.constants import RE_COMMA_WSP
from svg_polish.types import SVGLength, Unit

__all__ = ["properly_size_doc"]


def properly_size_doc(docElement: Element, options: optparse.Values) -> None:
    """Replace ``<svg width=… height=…>`` with a ``viewBox`` when safe.

    Reads the existing ``width`` / ``height`` / ``viewBox``; if a
    valid ``viewBox`` is already present and disagrees with the
    explicit size, leaves the document untouched. Otherwise sets
    ``viewBox="0 0 W H"`` and removes ``width`` / ``height``.

    The renderer-workaround branch (default on) refuses to convert
    when the size uses a physical unit — librsvg in particular
    renders such cases at the wrong scale once the explicit
    dimensions are gone.
    """
    w = SVGLength(docElement.getAttribute("width"))
    h = SVGLength(docElement.getAttribute("height"))

    # Browsers and vector editors handle non-px units fine, but
    # librsvg miscalculates the scale once width/height are gone.
    # Bail out unless the user explicitly opts out of the workaround.
    if options.renderer_workaround and (
        (w.units != Unit.NONE and w.units != Unit.PX) or (h.units != Unit.NONE and h.units != Unit.PX)
    ):
        return

    vbSep = RE_COMMA_WSP.split(docElement.getAttribute("viewBox"))
    if len(vbSep) == 4:
        try:
            # A non-zero viewBox origin shifts the rendering — we
            # can't safely overwrite it with "0 0 W H".
            vbX = float(vbSep[0])
            vbY = float(vbSep[1])
            if vbX != 0 or vbY != 0:
                return

            # If the existing viewBox dimensions don't match width/height,
            # the SVG was deliberately scaled — preserve it.
            vbWidth = float(vbSep[2])
            vbHeight = float(vbSep[3])
            if vbWidth != w.value or vbHeight != h.value:
                return
        except ValueError:  # pragma: no cover — viewBox values are scoured before reaching this point
            # An unparseable viewBox is invalid; safe to overwrite.
            pass

    docElement.setAttribute("viewBox", f"0 0 {w.value} {h.value}")
    docElement.removeAttribute("width")
    docElement.removeAttribute("height")
