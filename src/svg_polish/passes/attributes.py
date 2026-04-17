"""Drop inheritable attributes from a parent that no child actually inherits.

The companion of :mod:`svg_polish.groups`'s hoist pass. After
:func:`~svg_polish.groups.move_common_attributes_to_parent_group`
lifts shared properties up to a parent ``<g>``, that parent may now
hold attributes that none of its children inherit (because every
child overrides them with an explicit value of its own). Those
attributes are dead weight; this pass removes them.

A property is considered "inherited" by a child only when the child
either has no value for it or sets it explicitly to ``"inherit"``.
Any other value blocks inheritance and means the parent's attribute
is wasted bytes.

Recursive depth-first so children are simplified before the parent —
the more attributes the children carry explicitly, the more the
parent loses on its own attributes.
"""

from __future__ import annotations

from xml.dom import Node
from xml.dom.minidom import Element

__all__ = ["remove_unused_attributes_on_parent"]


# Inheritable presentation properties — must match the equivalent set
# in svg_polish.groups so the hoist/cleanup passes agree on what counts
# as a presentation property worth managing.
_INHERITABLE_PROPS: list[str] = [
    "clip-rule",
    "display-align",
    "fill",
    "fill-opacity",
    "fill-rule",
    "font",
    "font-family",
    "font-size",
    "font-size-adjust",
    "font-stretch",
    "font-style",
    "font-variant",
    "font-weight",
    "letter-spacing",
    "pointer-events",
    "shape-rendering",
    "stroke",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
    "text-decoration",
    "text-rendering",
    "visibility",
    "word-spacing",
    "writing-mode",
]


def remove_unused_attributes_on_parent(elem: Element) -> int:
    """Strip attributes from *elem* whose value no child inherits.

    Walks *elem*'s element children depth-first first (so nested
    parents shrink in one pass), then for each inheritable property
    on *elem*: if at least one child has its own non-inherit value
    for that property, no descendant inherits *elem*'s value and the
    attribute is removed.

    Skipped when *elem* has fewer than two element children — there
    is nothing to share among.

    Returns the number of attributes removed across *elem* and the
    whole subtree.
    """
    num = 0

    childElements = []
    for child in elem.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            childElements.append(child)
            num += remove_unused_attributes_on_parent(child)

    if len(childElements) <= 1:
        return num

    attrList = elem.attributes
    unusedAttrs: dict[str, str] = {}
    for index in range(attrList.length):
        attr = attrList.item(index)
        assert attr is not None
        if attr.nodeName in _INHERITABLE_PROPS:
            unusedAttrs[attr.nodeName] = attr.nodeValue or ""

    # A property is inherited when the child has no value (== "") or
    # explicitly opts in via "inherit". Any other value blocks
    # inheritance, so the parent's attribute reaches no descendant.
    for child in childElements:
        inheritedAttrs = []
        for name in unusedAttrs:
            val = child.getAttribute(name)
            if val in ("", "inherit"):
                inheritedAttrs.append(name)
        for a in inheritedAttrs:
            del unusedAttrs[a]

    for name in unusedAttrs:
        elem.removeAttribute(name)
        num += 1

    return num
