"""Strip XML attributes whose value matches the SVG/CSS default.

Two layers of defaults are handled:

* **Element-specific defaults** (``default_attributes_per_element``) —
  e.g. ``<rect x="0">`` → drop ``x``; ``<circle cy="0">`` → drop ``cy``.
  Values are typed (``DefaultAttribute``) and may carry a unit
  constraint and a predicate.
* **Inheritable presentation defaults** (``default_properties``) —
  e.g. ``fill="black"``, ``stroke="none"``. These are inheritable, so
  removing a default from a child whose ancestor sets a *non*-default
  value would change the rendering. The *tainted* set tracks which
  property names are dirty along the current path so a default value
  is only removed when no ancestor competes for that name.

The pass is recursive depth-first; *tainted* propagates downward and
is restored after each child via in-place set arithmetic
(``tainted &= snapshot``) — cheaper than ``tainted.copy()`` per child
on deep documents. Style declarations inside ``style="…"`` are
processed identically to attributes.
"""

from __future__ import annotations

import optparse
from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.constants import (
    DefaultAttribute,
    default_attributes_per_element,
    default_attributes_universal,
    default_properties,
)
from svg_polish.style import _get_style, _set_style
from svg_polish.types import SVGLength, Unit

__all__ = [
    "_iter_attr_names",
    "remove_default_attribute_value",
    "remove_default_attribute_values",
    "taint",
]


def _iter_attr_names(node: Element) -> list[str]:
    """Return *node*'s attribute names as a plain list of strings.

    Materialising the list once avoids repeating the
    ``NamedNodeMap.item(i).nodeName`` round-trip — see
    :func:`svg_polish.serialize.attributes_ordered_for_output` for the
    rationale on why ``.item(i)`` is the slow path here (bpo#40689).
    """
    attrs = node.attributes
    names: list[str] = []
    for idx in range(attrs.length):
        item = attrs.item(idx)
        if item is not None and item.nodeName is not None:
            names.append(item.nodeName)
    return names


def taint(taintedSet: set[str], taintedAttribute: str) -> set[str]:
    """Mark *taintedAttribute* and any related properties as set on this branch.

    The marker properties form a coupled group: setting any of
    ``marker-start`` / ``marker-mid`` / ``marker-end`` also implicitly
    taints the shorthand ``marker``, and setting ``marker`` taints all
    three long-form names. Without this widening, a child could remove
    a defaulted ``marker-end`` even though the parent set ``marker``,
    which would change rendering.
    """
    taintedSet.add(taintedAttribute)
    if taintedAttribute == "marker":
        taintedSet |= {"marker-start", "marker-mid", "marker-end"}
    if taintedAttribute in ["marker-start", "marker-mid", "marker-end"]:
        taintedSet.add("marker")
    return taintedSet


def remove_default_attribute_value(node: Element, attribute: DefaultAttribute) -> int:
    """Remove a single default attribute from *node* if every constraint passes.

    A default attribute is removable when:

    * the attribute is present, and
    * its value matches ``attribute.value`` (string compare for text;
      numeric compare via :class:`SVGLength` for numeric defaults), and
    * the value's unit matches ``attribute.units`` (or *units* is
      ``None`` which means "any"), and
    * ``attribute.conditions(node)`` returns truthy (or *conditions*
      is ``None``).

    Returns 1 when removed, 0 otherwise — the caller accumulates these
    into a global byte saving counter.
    """
    if not node.hasAttribute(attribute.name):
        return 0

    if isinstance(attribute.value, str):
        if node.getAttribute(attribute.name) == attribute.value and (
            (attribute.conditions is None) or attribute.conditions(node)
        ):
            node.removeAttribute(attribute.name)
            return 1
        return 0

    nodeValue = SVGLength(node.getAttribute(attribute.name))
    value_matches = (attribute.value is None) or (
        (nodeValue.value == attribute.value) and nodeValue.units != Unit.INVALID
    )
    units_match = (
        (attribute.units is None)
        or (nodeValue.units == attribute.units)
        or (isinstance(attribute.units, list) and nodeValue.units in attribute.units)
    )
    conditions_pass = (attribute.conditions is None) or attribute.conditions(node)
    if value_matches and units_match and conditions_pass:
        node.removeAttribute(attribute.name)
        return 1
    return 0


def remove_default_attribute_values(
    node: Element,
    options: optparse.Values,
    tainted: set[str] | None = None,
) -> int:
    """Recursively strip attributes whose values equal the SVG/CSS default.

    Two-pass per element:

    1. **Element-specific defaults** — iterate the (small) typed
       ``DefaultAttribute`` lists ``default_attributes_universal``
       (always empty in practice — kept as an extension point) and
       ``default_attributes_per_element[node.nodeName]``.
    2. **Inheritable property defaults** — for each attribute name on
       *node* (and each style declaration), drop it when its value
       matches the entry in ``default_properties`` *and* the name is
       not in *tainted*. A non-matching value taints the name so
       descendants can't remove it either.

    Args:
        node: Subtree root. Non-element nodes return 0 immediately so
            the caller can pass any DOM child without a type check.
        options: Reserved — currently unused, kept so future per-flag
            tweaks don't change the signature.
        tainted: Property names set to a non-default value somewhere
            on the path from the document root to *node*. ``None`` at
            the top-level call.

    Returns:
        Total attributes plus style declarations removed.
    """
    num = 0
    if node.nodeType != Node.ELEMENT_NODE:
        return 0

    if tainted is None:
        tainted = set()

    # Element-specific defaults — split into a (currently empty)
    # universal list and a per-element table to avoid scanning
    # irrelevant entries on every node.
    for (
        attribute
    ) in default_attributes_universal:  # pragma: no cover — list is always empty (no universal defaults defined)
        num += remove_default_attribute_value(node, attribute)
    if node.nodeName in default_attributes_per_element:
        for attribute in default_attributes_per_element[node.nodeName]:
            num += remove_default_attribute_value(node, attribute)

    # Inheritable property defaults — XML attributes first.
    attributes = _iter_attr_names(node)
    for attr_name in attributes:
        if attr_name not in tainted and attr_name in default_properties:
            if node.getAttribute(attr_name) == default_properties[attr_name]:
                node.removeAttribute(attr_name)
                num += 1
            else:
                tainted = taint(tainted, attr_name)
    # ...then the same logic for style="…" declarations.
    styles = _get_style(node)
    for attr_name in list(styles):
        if attr_name not in tainted and attr_name in default_properties:
            if styles[attr_name] == default_properties[attr_name]:
                del styles[attr_name]
                num += 1
            else:
                tainted = taint(tainted, attr_name)
    _set_style(node, styles)

    # Snapshot once and restore in-place after each child instead of
    # tainted.copy() per child. Saves N-1 set allocations per level on
    # deep documents.
    tainted_before_children = set(tainted)
    for child in node.childNodes:
        # childNodes' static type is broad; the early Node.ELEMENT_NODE
        # check at the top of this function filters non-Elements at runtime.
        num += remove_default_attribute_values(child, options, tainted)  # type: ignore[arg-type]
        tainted &= tainted_before_children

    return num
