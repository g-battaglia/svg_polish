"""Style attribute parsing, repair, and inheritance analysis.

The optimizer's ``repair_style`` pass cleans up the inline ``style="…"``
attribute on every element: fixing malformed declarations, eliding
properties that are made redundant by other declarations
(``stroke="none"`` invalidates ``stroke-width``, …), folding font-only
properties on non-text elements, and promoting style declarations to
matching XML attributes when ``style_to_xml`` is set.

The supporting helpers (``_get_style``, ``_set_style``,
``_invalidate_style_cache``) own the per-node parsed-style cache
(``node._cachedStyle``); the inheritance walks
(``style_inherited_from_parent``, ``style_inherited_by_child``) tell the
repair pass whether dropping a property would actually change rendering.

``may_contain_text_nodes`` lives here because the repair pass relies on
it to decide when font-related properties are safe to drop.
"""

from __future__ import annotations

import optparse
from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.constants import NS, svgAttributes
from svg_polish.types import StyleMap, SVGLength, Unit


def _try_float(value: str) -> float | None:
    """Parse *value* as a float, returning None for non-numeric inputs.

    Used by :func:`repair_style` to skip optimizations that compare a style
    property against zero when the value is a CSS function (``var(--x)``,
    ``calc(...)``), a keyword (``inherit``, ``currentColor``), or anything
    else that ``float()`` cannot handle. Scour 0.38.2 raises ``ValueError``
    in this situation; svg_polish prefers to leave the property untouched.
    """
    try:
        return float(value)
    except ValueError:
        return None


__all__ = [
    "_get_style",
    "_invalidate_style_cache",
    "_set_style",
    "may_contain_text_nodes",
    "repair_style",
    "style_inherited_by_child",
    "style_inherited_from_parent",
]


def _get_style(node: Element) -> StyleMap:
    """Return the ``style`` attribute of *node* as a ``{property: value}`` dict.

    Results are cached on the node (``node._cachedStyle``) to avoid
    repeated string parsing — the cache is invalidated by
    :func:`_set_style` and :func:`_invalidate_style_cache`. The cache
    stores the dict instance directly, so callers should treat the
    returned mapping as the authoritative copy.
    """
    if node.nodeType != Node.ELEMENT_NODE:
        return {}
    cached: StyleMap | None = getattr(node, "_cachedStyle", None)
    if cached is not None:
        return cached
    style_attribute = node.getAttribute("style")
    if style_attribute:
        styleMap: StyleMap = {}
        for style in style_attribute.split(";"):
            propval = style.split(":")
            if len(propval) == 2:
                styleMap[propval[0].strip()] = propval[1].strip()
        node._cachedStyle = styleMap  # type: ignore[attr-defined]
        return styleMap
    empty: StyleMap = {}
    node._cachedStyle = empty  # type: ignore[attr-defined]
    return empty


def _set_style(node: Element, styleMap: StyleMap) -> Element:
    """Set the ``style`` attribute of *node* from *styleMap* and update the cache.

    Empty style maps are persisted as a removed attribute (rather than
    ``style=""``) so the serializer's attribute-ordering pass doesn't
    have to special-case them.
    """
    node._cachedStyle = styleMap  # type: ignore[attr-defined]
    fixedStyle = ";".join(prop + ":" + styleMap[prop] for prop in styleMap)
    if fixedStyle:
        node.setAttribute("style", fixedStyle)
    elif node.getAttribute("style"):
        node.removeAttribute("style")
    return node


def _invalidate_style_cache(node: Element) -> None:
    """Clear the cached style dict so the next :func:`_get_style` re-parses.

    Call this whenever you mutate ``node.style`` directly without going
    through :func:`_set_style` (e.g. after rewriting ``url(#…)``
    references inside the style string).
    """
    node._cachedStyle = None  # type: ignore[attr-defined]


def repair_style(node: Element, options: optparse.Values) -> int:
    """Fix broken style declarations and elide ones made redundant by others.

    Walks *node* and its descendants. Returns the number of style
    declarations removed across the subtree. The pass:

    * Repairs ``fill: url(#x) rgb(0,0,0)`` (Inkscape sometimes emits
      this) by dropping the trailing colour.
    * Drops fill/stroke siblings when ``opacity:0``,
      ``fill-opacity:0``, ``stroke-opacity:0``, ``stroke-width:0`` or
      ``fill:none`` / ``stroke:none`` make them ineffective — but only
      if no descendant inherits the property.
    * Strips font-related declarations from elements that can't render
      text (:func:`may_contain_text_nodes`).
    * Drops ``-inkscape-font-specification`` and other Inkscape
      vendor properties.
    * Trims ``overflow`` declarations on elements where the property
      doesn't apply or where the default is already in effect.
    * When ``options.style_to_xml`` is set, hoists declarations whose
      property name is also a presentation attribute to a real XML
      attribute (saves bytes and survives un-styled rendering).
    """
    num = 0
    styleMap = _get_style(node)
    if styleMap:
        # I've seen this enough to know that I need to correct it:
        # fill: url(#linearGradient4918) rgb(0, 0, 0);
        for prop in ["fill", "stroke"]:
            if prop in styleMap:
                chunk = styleMap[prop].split(") ")
                if (
                    len(chunk) == 2
                    and (chunk[0].startswith("url(#") or chunk[0].startswith('url("#') or chunk[0].startswith("url('#"))
                    and chunk[1] == "rgb(0, 0, 0)"
                ):
                    styleMap[prop] = chunk[0] + ")"
                    num += 1

        # Here is where we can weed out unnecessary styles like:
        #  opacity:1
        if "opacity" in styleMap:
            opacity = _try_float(styleMap["opacity"])
            # if opacity='0' then all fill and stroke properties are useless, remove them
            if opacity == 0.0:
                for uselessStyle in [
                    "fill",
                    "fill-opacity",
                    "fill-rule",
                    "stroke",
                    "stroke-linejoin",
                    "stroke-opacity",
                    "stroke-miterlimit",
                    "stroke-linecap",
                    "stroke-dasharray",
                    "stroke-dashoffset",
                    "stroke-opacity",
                ]:
                    if uselessStyle in styleMap and not style_inherited_by_child(node, uselessStyle):
                        del styleMap[uselessStyle]
                        num += 1

        #  if stroke:none, then remove all stroke-related properties (stroke-width, etc)
        #  TODO: should also detect if the computed value of this element is stroke="none"
        if "stroke" in styleMap and styleMap["stroke"] == "none":
            for strokestyle in [
                "stroke-width",
                "stroke-linejoin",
                "stroke-miterlimit",
                "stroke-linecap",
                "stroke-dasharray",
                "stroke-dashoffset",
                "stroke-opacity",
            ]:
                if strokestyle in styleMap and not style_inherited_by_child(node, strokestyle):
                    del styleMap[strokestyle]
                    num += 1
            # we need to properly calculate computed values
            if not style_inherited_by_child(node, "stroke") and style_inherited_from_parent(node, "stroke") in [
                None,
                "none",
            ]:
                del styleMap["stroke"]
                num += 1

        #  if fill:none, then remove all fill-related properties (fill-rule, etc)
        if "fill" in styleMap and styleMap["fill"] == "none":
            for fillstyle in ["fill-rule", "fill-opacity"]:
                if fillstyle in styleMap and not style_inherited_by_child(node, fillstyle):
                    del styleMap[fillstyle]
                    num += 1

        #  fill-opacity: 0
        if "fill-opacity" in styleMap:
            fillOpacity = _try_float(styleMap["fill-opacity"])
            if fillOpacity == 0.0:
                for uselessFillStyle in ["fill", "fill-rule"]:
                    if uselessFillStyle in styleMap and not style_inherited_by_child(node, uselessFillStyle):
                        del styleMap[uselessFillStyle]
                        num += 1

        #  stroke-opacity: 0
        if "stroke-opacity" in styleMap:
            strokeOpacity = _try_float(styleMap["stroke-opacity"])
            if strokeOpacity == 0.0:
                for uselessStrokeStyle in [
                    "stroke",
                    "stroke-width",
                    "stroke-linejoin",
                    "stroke-linecap",
                    "stroke-dasharray",
                    "stroke-dashoffset",
                ]:
                    if uselessStrokeStyle in styleMap and not style_inherited_by_child(node, uselessStrokeStyle):
                        del styleMap[uselessStrokeStyle]
                        num += 1

        # stroke-width: 0
        if "stroke-width" in styleMap:
            strokeWidth = SVGLength(styleMap["stroke-width"])
            # SVGLength returns value=0 with units=INVALID for unparseable inputs
            # (var(--x), calc(...), inherit, …) — those must NOT be treated as 0.
            if strokeWidth.units != Unit.INVALID and strokeWidth.value == 0.0:
                for uselessStrokeStyle in [
                    "stroke",
                    "stroke-linejoin",
                    "stroke-linecap",
                    "stroke-dasharray",
                    "stroke-dashoffset",
                    "stroke-opacity",
                ]:
                    if uselessStrokeStyle in styleMap and not style_inherited_by_child(node, uselessStrokeStyle):
                        del styleMap[uselessStrokeStyle]
                        num += 1

        # remove font properties for non-text elements
        # I've actually observed this in real SVG content
        if not may_contain_text_nodes(node):
            for fontstyle in [
                "font-family",
                "font-size",
                "font-stretch",
                "font-size-adjust",
                "font-style",
                "font-variant",
                "font-weight",
                "letter-spacing",
                "line-height",
                "kerning",
                "text-align",
                "text-anchor",
                "text-decoration",
                "text-rendering",
                "unicode-bidi",
                "word-spacing",
                "writing-mode",
            ]:
                if fontstyle in styleMap:
                    del styleMap[fontstyle]
                    num += 1

        # remove inkscape-specific styles
        # TODO: need to get a full list of these
        for inkscapeStyle in ["-inkscape-font-specification"]:
            if inkscapeStyle in styleMap:
                del styleMap[inkscapeStyle]
                num += 1

        if "overflow" in styleMap:
            # remove overflow from elements to which it does not apply,
            # see https://www.w3.org/TR/SVG/masking.html#OverflowProperty
            if node.nodeName not in ["svg", "symbol", "image", "foreignObject", "marker", "pattern"]:
                del styleMap["overflow"]
                num += 1
            # if the node is not the root <svg> element the SVG's user agent
            # style sheet overrides the initial value with ``hidden``, which
            # can consequently be removed (see last bullet point in the link
            # above). For the root <svg> element the CSS2 default
            # ``overflow="visible"`` is the initial value and is removable.
            elif node.ownerDocument is not None and node != node.ownerDocument.documentElement:
                if styleMap["overflow"] == "hidden":
                    del styleMap["overflow"]
                    num += 1
            elif styleMap["overflow"] == "visible":
                del styleMap["overflow"]
                num += 1

        # now if any of the properties match known SVG attributes we prefer attributes
        # over style so emit them and remove them from the style map
        if options.style_to_xml:
            for propName in list(styleMap):
                if propName in svgAttributes:
                    node.setAttribute(propName, styleMap[propName])
                    del styleMap[propName]

        _set_style(node, styleMap)

    # Recurse into child elements. Non-Element nodes are short-circuited
    # by the early return inside :func:`_get_style`.
    for child in node.childNodes:
        num += repair_style(child, options)  # type: ignore[arg-type]

    return num


def style_inherited_from_parent(node: Element, style: str) -> str | None:
    """Return the inherited value of *style* from ancestor elements, or ``None``.

    Walks ancestors until a non-``inherit`` value is found. Considers
    presentation attributes and inline styles only — style sheets are
    ignored, which is consistent with the rest of the optimizer's
    style handling and is acceptable because the result drives a
    "remove if redundant" decision (a wrong ``None`` keeps the
    declaration; a wrong concrete value is impossible).
    """
    parentNode = node.parentNode

    if parentNode is None or parentNode.nodeType == Node.DOCUMENT_NODE:
        return None

    # check styles first (they take precedence over presentation attributes)
    styles = _get_style(parentNode)  # type: ignore[arg-type]
    if style in styles:
        value = styles[style]
        if value != "inherit":
            return value

    # check attributes
    value = parentNode.getAttribute(style)  # type: ignore[union-attr]
    if value not in ["", "inherit"]:
        return parentNode.getAttribute(style)  # type: ignore[union-attr]

    # check the next parent recursively if we did not find a value yet
    return style_inherited_from_parent(parentNode, style)  # type: ignore[arg-type]


def style_inherited_by_child(node: Element, style: str, nodeIsChild: bool = False) -> bool:
    """Return whether *style* is inherited by any descendant of *node*.

    A ``False`` result means the style can safely be removed from
    *node* without affecting rendering. ``True`` means at least one
    descendant relies on the inherited value (or the descendant is a
    leaf that could render text/strokes), so the property must stay.

    Same caveat as :func:`style_inherited_from_parent`: presentation
    attributes and inline styles only; ``<style>`` blocks are ignored.

    The ``nodeIsChild`` flag distinguishes the entry call (the property
    holder) from the recursive descents (children that may shadow the
    inherited value with their own declaration).
    """
    # Comment, text and CDATA nodes don't have attributes and aren't containers.
    if node.nodeType != Node.ELEMENT_NODE:
        return False

    if nodeIsChild:
        # If the current child node sets a new value for the property
        # we can stop the search in the current branch.
        if node.getAttribute(style) not in ["", "inherit"]:
            return False
        styles = _get_style(node)
        if (style in styles) and styles[style] != "inherit":
            return False
    elif not node.childNodes:
        # No children: the property cannot be inherited from anywhere.
        return False

    # Recurse into children.
    if node.childNodes:
        for child in node.childNodes:
            if style_inherited_by_child(child, style, True):  # type: ignore[arg-type]
                return True

    # Container elements never propagate the inherited value to a
    # consumer (because no descendant relies on it). Anything else
    # (leaves, text nodes, unknown SVG elements, …) keeps the property.
    return node.nodeName not in [
        "a",
        "defs",
        "glyph",
        "g",
        "marker",
        "mask",
        "missing-glyph",
        "pattern",
        "svg",
        "switch",
        "symbol",
    ]


def may_contain_text_nodes(node: Element) -> bool:
    """Return ``True`` if *node* (or any descendant) may render text content.

    The result is cached as ``node.may_contain_text_nodes`` so repeated
    queries (e.g. one per font-related property in :func:`repair_style`)
    don't re-walk the subtree.

    A ``False`` result is a guarantee that text-based attributes can
    be removed from *node* without changing rendering. ``True`` keeps
    them — the conservative default for elements outside the SVG
    namespace and unknown SVG elements.
    """
    cached: bool | None = getattr(node, "may_contain_text_nodes", None)
    if cached is not None:
        return cached

    result = True
    if node.nodeType != Node.ELEMENT_NODE:
        result = False
    elif node.namespaceURI != NS["SVG"]:
        # Non-SVG elements: unknown — assume yes.
        result = True
    elif node.nodeName in ["rect", "circle", "ellipse", "line", "polygon", "polyline", "path", "image", "stop"]:
        # Blacklisted SVG elements that never contain text.
        result = False
    elif node.nodeName in ["g", "clipPath", "marker", "mask", "pattern", "linearGradient", "radialGradient", "symbol"]:
        # Group elements: walk children to see if any are text-bearing.
        result = False
        for child in node.childNodes:
            if may_contain_text_nodes(child):  # type: ignore[arg-type]
                result = True
    # Everything else stays at the default of True (future SVG text
    # elements at best, unknown at worst).

    node.may_contain_text_nodes = result  # type: ignore[attr-defined]
    return result
