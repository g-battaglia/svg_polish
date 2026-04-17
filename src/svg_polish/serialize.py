"""XML serialization for the SVG output stage of the optimizer.

This module owns the *output* side of the pipeline: turning an in-memory
DOM tree back into a well-formed SVG string. The functions here are pure
(they never mutate the DOM) and depend only on :mod:`xml.dom.minidom`,
:mod:`optparse`, and the constants in :mod:`svg_polish.constants`, which
keeps them safe to call from any pass.

The public surface is :func:`serialize_xml`. The other functions
(:func:`make_well_formed`, :func:`choose_quote_character`,
:func:`attributes_ordered_for_output`) are exposed because individual
optimizer passes occasionally need to escape a value or sort attributes
without serializing a whole subtree.

Indentation, whitespace handling, attribute ordering, quote selection and
``xml:space`` semantics are all implemented here — see
:func:`serialize_xml` for the full spec.
"""

from __future__ import annotations

import optparse
from xml.dom import Node
from xml.dom.minidom import Attr, Element

from svg_polish.constants import (
    _RE_MULTI_SPACE,
    KNOWN_ATTRS_ORDER_BY_NAME,
    TEXT_CONTENT_ELEMENTS,
    XML_ENTS_ESCAPE_APOS,
    XML_ENTS_ESCAPE_QUOT,
    XML_ENTS_NO_QUOTES,
)

__all__ = [
    "attributes_ordered_for_output",
    "choose_quote_character",
    "make_well_formed",
    "serialize_xml",
]


def make_well_formed(text: str, quote_dict: dict[str, str] | None = None) -> str:
    """Escape XML special characters in *text* using *quote_dict*.

    The quote-able characters (``<``, ``>``, ``&`` plus optionally ``"`` or
    ``'``) are quite rare in SVG — they mostly only occur inside text
    elements in practice. Therefore the function takes a fast path that
    returns *text* unchanged when none of the entity-mapped characters are
    present, avoiding the per-character generator-expression cost on the
    hot output path.

    Args:
        text: The string to escape.
        quote_dict: Map ``character → entity``. Defaults to
            :data:`XML_ENTS_NO_QUOTES`. For attribute values use
            :data:`XML_ENTS_ESCAPE_QUOT` or :data:`XML_ENTS_ESCAPE_APOS`
            depending on the chosen quote character.

    Returns:
        The escaped string, or *text* itself if no escaping was required.
    """
    if quote_dict is None:
        quote_dict = XML_ENTS_NO_QUOTES
    if not any(c in text for c in quote_dict):
        return text
    return "".join(quote_dict.get(c, c) for c in text)


def choose_quote_character(value: str, prefer: str = "double") -> tuple[str, dict[str, str]]:
    """Pick ``"`` or ``'`` for an attribute, honouring *prefer* unless escapes mount.

    *prefer* is the user-requested delimiter (``"double"`` or ``"single"``).
    The function returns the preferred delimiter unless the value contains
    enough occurrences of it to make the alternative delimiter cheaper —
    the output is therefore always well-formed regardless of the value.

    The associated XML-entity escape map is returned alongside so the caller
    can pass it straight into :func:`make_well_formed`.
    """
    quot_count = value.count('"')
    apos_count = value.count("'")
    if prefer == "single":
        # Single quotes preferred unless the value carries strictly more
        # apostrophes than double-quotes (then double-quoting is cheaper).
        if apos_count == 0 or apos_count <= quot_count:
            return "'", XML_ENTS_ESCAPE_APOS
        return '"', XML_ENTS_ESCAPE_QUOT
    # ``"double"`` (default): mirror the previous behaviour.
    if quot_count == 0 or quot_count <= apos_count:
        return '"', XML_ENTS_ESCAPE_QUOT
    return "'", XML_ENTS_ESCAPE_APOS


def _attribute_sort_key_function(attribute: Attr) -> tuple[int, str]:
    """Sort key for attributes: known SVG attributes first, then alphabetical.

    The ``KNOWN_ATTRS_ORDER_BY_NAME`` table assigns a small integer to every
    attribute the SVG spec lists, leaving unknown attributes at the
    sentinel max-value so they trail in alphabetical order. Returning a
    ``(order, name)`` tuple makes :func:`sorted` stable and lexicographic
    within each rank.
    """
    name = attribute.name
    order_value = KNOWN_ATTRS_ORDER_BY_NAME[name]
    return order_value, name


def attributes_ordered_for_output(element: Element) -> list[Attr]:
    """Return *element*'s attributes sorted in canonical SVG output order.

    Empty attribute lists short-circuit so the hot path on attribute-less
    elements avoids the ``NamedNodeMap.item`` round-trip. The .item(i) call
    is painfully slow (bpo#40689), so we materialise the items once and
    then sort the Python list.
    """
    if not element.hasAttributes():
        return []
    attribute = element.attributes
    # ``attribute.values()`` would be faster but is marked experimental in
    # the standard library, so we stick with .item(i) and pay the cost once.
    items = [attribute.item(i) for i in range(attribute.length)]
    # minidom's NamedNodeMap.item returns Node | None; in practice only Attr
    # nodes are stored on element.attributes. Filter Nones and cast for mypy.
    attrs: list[Attr] = [a for a in items if a is not None]  # type: ignore[misc]
    return sorted(attrs, key=_attribute_sort_key_function)


def serialize_xml(
    element: Element,
    options: optparse.Values,
    indent_depth: int = 0,
    preserveWhitespace: bool = False,
) -> str:
    """Serialize a DOM tree to an SVG string with pretty-printing and ordering.

    Produces well-formed XML output from a DOM element tree. Handles
    indentation, whitespace normalization, quote choice, XML escaping,
    and special treatment of SVG text content elements.

    **Indentation**: When ``options.newlines`` is True, child elements are
    placed on new lines and indented with ``options.indent_type`` (``"tab"``
    or ``"space"``) repeated ``options.indent_depth`` times per level. When
    False, everything is emitted on a single line with no extra whitespace.

    **Text content elements**: Elements in :data:`TEXT_CONTENT_ELEMENTS`
    (``<text>``, ``<tspan>``, ``<tref>``, ``<textPath>``, etc.) receive
    no indentation — whitespace inside them is significant per the SVG spec
    (``<text>foo</text>`` ≠ ``<text> foo </text>``). Text nodes inside
    these elements have newlines stripped, tabs replaced with spaces, and
    multiple spaces collapsed to one, following the SVG whitespace rules
    at https://www.w3.org/TR/SVG/text.html#WhiteSpace.

    **Quote choice**: Attribute values are examined for single/double quotes
    via :func:`choose_quote_character` and the appropriate XML entity map
    is applied by :func:`make_well_formed`.

    **Attribute ordering**: Attributes are reordered for consistent output
    via :func:`attributes_ordered_for_output`. The ``style`` attribute's
    declarations are sorted alphabetically and joined with ``;``.

    **xml:space**: The ``xml:space`` attribute is honored — ``"preserve"``
    enables whitespace preservation for the subtree, ``"default"`` disables
    it.

    Args:
        element: The root DOM element to serialize.
        options: Serializer options (``newlines``, ``indent_type``,
            ``indent_depth``, ``strip_xml_space_attribute``).
        indent_depth: Current nesting level (incremented for each child
            element). Pass 0 for the top-level call.
        preserveWhitespace: If True, whitespace in text nodes is left
            untouched. Propagated to child calls when ``xml:space="preserve"``
            is set.

    Returns:
        A well-formed SVG/XML string representation of *element* and its
        descendants. No trailing newline is added.
    """
    outParts = []

    indent_type = ""
    newline = ""
    if options.newlines:
        if options.indent_type == "tab":
            indent_type = "\t"
        elif options.indent_type == "space":
            indent_type = " "
        indent_type *= options.indent_depth
        newline = "\n"

    outParts.extend([(indent_type * indent_depth), "<", element.nodeName])

    # Attributes are sorted into canonical SVG output order.
    # ``attr_quote`` is part of OptimizeOptions but the legacy bridge tunnels
    # through optparse.Values; getattr keeps callers that build a bare
    # ``optparse.Values`` (e.g. legacy tests) working without surprises.
    attr_quote_pref = getattr(options, "attr_quote", "double")
    attrs = attributes_ordered_for_output(element)
    for attr in attrs:
        attrValue = attr.nodeValue
        quote, xml_ent = choose_quote_character(attrValue, attr_quote_pref)
        attrValue = make_well_formed(attrValue, xml_ent)

        if attr.nodeName == "style":
            # sort declarations
            attrValue = ";".join(sorted(attrValue.split(";")))

        outParts.append(" ")
        # preserve xmlns: if it is a namespace prefix declaration
        if attr.prefix is not None:
            outParts.extend([attr.prefix, ":"])
        elif attr.namespaceURI is not None:
            if (
                attr.namespaceURI == "http://www.w3.org/2000/xmlns/" and attr.nodeName.find("xmlns") == -1
            ):  # pragma: no cover — minidom always includes xmlns in nodeName for namespace declarations
                outParts.append("xmlns:")
            elif attr.namespaceURI == "http://www.w3.org/1999/xlink":
                outParts.append("xlink:")
        outParts.extend([attr.localName, "=", quote, attrValue, quote])

        if attr.nodeName == "xml:space":
            if attrValue == "preserve":
                preserveWhitespace = True
            elif attrValue == "default":
                preserveWhitespace = False

    children = element.childNodes
    if children.length == 0:
        outParts.append("/>")
    else:
        outParts.append(">")

        onNewLine = False
        for child in element.childNodes:
            # element node
            if child.nodeType == Node.ELEMENT_NODE:
                # Text content elements treat whitespace as significant: do
                # not indent inside them. See
                #    https://www.w3.org/TR/SVG/text.html#WhiteSpace
                if preserveWhitespace or element.nodeName in TEXT_CONTENT_ELEMENTS:
                    outParts.append(serialize_xml(child, options, 0, preserveWhitespace))
                else:
                    outParts.extend([newline, serialize_xml(child, options, indent_depth + 1, preserveWhitespace)])
                    onNewLine = True
            # text node
            elif child.nodeType == Node.TEXT_NODE:
                text_content = child.nodeValue
                if not preserveWhitespace:
                    # Strip / consolidate whitespace according to spec, see
                    #    https://www.w3.org/TR/SVG/text.html#WhiteSpace
                    if element.nodeName in TEXT_CONTENT_ELEMENTS:
                        text_content = text_content.replace("\n", "")
                        text_content = text_content.replace("\t", " ")
                        if child == element.firstChild:
                            text_content = text_content.lstrip()
                        elif child == element.lastChild:
                            text_content = text_content.rstrip()
                        text_content = _RE_MULTI_SPACE.sub(" ", text_content)
                    else:
                        text_content = text_content.strip()
                outParts.append(make_well_formed(text_content))
            # CDATA node
            # mypy's xml.dom.minidom stubs do not include CDATASection in the
            # childNodes union, but the runtime can produce it (parseString
            # preserves <![CDATA[…]]> blocks unchanged).
            elif child.nodeType == Node.CDATA_SECTION_NODE:  # type: ignore[comparison-overlap]
                outParts.extend(["<![CDATA[", child.nodeValue, "]]>"])
            # Comment node
            elif child.nodeType == Node.COMMENT_NODE:
                outParts.extend([newline, indent_type * (indent_depth + 1), "<!--", child.nodeValue, "-->"])
            # TODO: entities, processing instructions, what else?
            else:  # pragma: no cover — no other node types expected
                pass

        if onNewLine:
            outParts.append(newline)
            outParts.append(indent_type * indent_depth)
        outParts.extend(["</", element.nodeName, ">"])

    return "".join(outParts)
