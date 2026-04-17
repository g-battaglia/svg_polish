"""Group-element optimisations: collapse, merge, and synthesise ``<g>``.

Three classes of transformation live here, each independently
byte-monotonic:

* **Collapse** — :func:`remove_nested_groups` strips a ``<g>`` whose only
  job is to wrap children (no attributes, no ``<title>`` / ``<desc>``).
  The children are promoted into the parent and the wrapper is unlinked.
* **Hoist** — :func:`move_common_attributes_to_parent_group` walks the
  tree depth-first; when every child of an element shares the same value
  for an inheritable presentation property (``fill``, ``stroke``,
  ``font-*`` …), the property is removed from each child and set on the
  parent. The child must not itself be referenced from elsewhere
  (``<use href="#…">``) — moving the attribute would change the rendered
  result.
* **Merge** — :func:`merge_sibling_groups_with_common_attributes` collapses
  consecutive ``<g>`` siblings whose attribute sets are byte-identical
  into a single ``<g>``.
* **Synthesise** — :func:`create_groups_for_common_attributes` is the
  inverse direction: when 3+ contiguous siblings share an attribute value
  but the parent isn't a ``<g>``, wrap them in a fresh ``<g>`` so a
  subsequent hoist pass can lift the attribute up. Runs of <3 are not
  worth wrapping (the new ``<g>`` plus tag bytes outweighs the saving).

The mergeable predicate :func:`g_tag_is_mergeable` is shared by
collapse and merge: both need to leave alone any ``<g>`` whose
``<title>`` / ``<desc>`` would lose its anchor if merged away.
"""

from __future__ import annotations

from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.constants import NS
from svg_polish.stats import ScourStats
from svg_polish.types import ReferencedIDs

__all__ = [
    "create_groups_for_common_attributes",
    "g_tag_is_mergeable",
    "merge_sibling_groups_with_common_attributes",
    "move_common_attributes_to_parent_group",
    "remove_nested_groups",
]


# Inheritable presentation properties from
# http://www.w3.org/TR/SVG11/propidx.html and
# http://www.w3.org/TR/SVGTiny12/attributeTable.html.
# Used by both move_common_attributes_to_parent_group and
# create_groups_for_common_attributes — these two functions MUST agree on
# the set, otherwise the synthesise pass would create groups around
# attributes that the hoist pass wouldn't subsequently lift.
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


# Element types allowed as direct children of <g> per SVG 1.1
# (https://www.w3.org/TR/SVG/struct.html#GElement) plus the SVG 1.2 Tiny
# additions (https://www.w3.org/TR/SVGTiny12/elementTable.html). Used by
# create_groups_for_common_attributes to decide which siblings can be
# wrapped in a new <g>; an element outside this set would be invalid as
# a <g> child and breaks the SVG content model.
_GROUPABLE_CHILDREN: list[str] = [
    # SVG 1.1 — animation elements
    "animate",
    "animateColor",
    "animateMotion",
    "animateTransform",
    "set",
    # descriptive elements
    "desc",
    "metadata",
    "title",
    # shape elements
    "circle",
    "ellipse",
    "line",
    "path",
    "polygon",
    "polyline",
    "rect",
    # structural elements
    "defs",
    "g",
    "svg",
    "symbol",
    "use",
    # gradient elements
    "linearGradient",
    "radialGradient",
    # other graphical elements
    "a",
    "altGlyphDef",
    "clipPath",
    "color-profile",
    "cursor",
    "filter",
    "font",
    "font-face",
    "foreignObject",
    "image",
    "marker",
    "mask",
    "pattern",
    "script",
    "style",
    "switch",
    "text",
    "view",
    # SVG 1.2 Tiny additions
    "animation",
    "audio",
    "discard",
    "handler",
    "listener",
    "prefetch",
    "solidColor",
    "textArea",
    "video",
]


def g_tag_is_mergeable(node: Element) -> bool:
    """Return True when *node* (a ``<g>``) is safe to collapse or merge.

    A ``<g>`` is *not* mergeable if it contains a direct ``<title>`` or
    ``<desc>`` child in the SVG namespace: those elements provide the
    accessible name / description for the group, and merging would either
    move them under a different ancestor (changing semantics) or duplicate
    them. Both :func:`remove_nested_groups` and
    :func:`merge_sibling_groups_with_common_attributes` consult this
    predicate before touching a ``<g>``.
    """
    return not any(
        n.nodeType == Node.ELEMENT_NODE and n.nodeName in ("title", "desc") and n.namespaceURI == NS["SVG"]
        for n in node.childNodes
    )


def remove_nested_groups(node: Element, stats: ScourStats) -> int:
    """Collapse attribute-less ``<g>`` wrappers, promoting children up one level.

    Recursive (top-down): the function visits *node*, removes its
    eligible ``<g>`` children, then recurses into every remaining
    element. A ``<g>`` is eligible only when:

    * it is in the SVG namespace,
    * it carries no attributes, and
    * :func:`g_tag_is_mergeable` returns True (no ``<title>`` /
      ``<desc>`` child).

    ``<switch>`` parents are skipped entirely: per the SVG content model,
    the switch picks one of its ``<g>`` children based on system
    requirements and collapsing the wrapper would change semantics
    (Scour bug #594930).
    """
    num = 0

    groupsToRemove = []
    # Skip <switch>: collapsing a <g> child of <switch> would alter
    # which alternative the switch selects.
    if not (node.nodeType == Node.ELEMENT_NODE and node.nodeName == "switch"):
        for child in node.childNodes:
            if (
                child.nodeName == "g"
                and child.namespaceURI == NS["SVG"]
                and len(child.attributes) == 0
                and g_tag_is_mergeable(child)
            ):
                groupsToRemove.append(child)

    for g in groupsToRemove:
        g_parent = g.parentNode
        assert g_parent is not None
        while g.childNodes.length > 0:
            first_child = g.firstChild
            assert first_child is not None
            g_parent.insertBefore(first_child, g)  # type: ignore[type-var]
        g_parent.removeChild(g)

    num += len(groupsToRemove)
    stats.num_elements_removed += len(groupsToRemove)

    for child in node.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            num += remove_nested_groups(child, stats)
    return num


def move_common_attributes_to_parent_group(elem: Element, referencedElements: ReferencedIDs) -> int:
    """Hoist inheritable presentation properties from children to *elem*.

    Recursive depth-first: children are processed before their parent so
    multi-level hoists collapse upward in a single pass. For each child
    of *elem* the function intersects the child's inheritable attributes
    (see :data:`_INHERITABLE_PROPS`) with the running ``commonAttrs``
    map; whatever survives is removed from every child and set on
    *elem*.

    **Skipped cases** (returns early or refuses to move attributes):

    * Children whose ``id`` is in *referencedElements* are excluded — a
      ``<use href="#child">`` somewhere else in the document would render
      differently if a presentation property moved off the original.
    * Parents with non-whitespace text children are skipped entirely:
      an inheritable property on the parent would also affect the text,
      changing its appearance.
    * Elements with fewer than two element children skip the hoist —
      there's nothing to share.
    * ``<set>`` / ``<animate*>`` children are excluded from the
      intersection because their ``fill="freeze|remove"`` attribute is
      not a presentation property despite the name collision.

    Returns the net byte saving (``(num_children - 1) × num_attrs``).
    """
    num = 0

    childElements = []
    for child in elem.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            if child.getAttribute("id") not in referencedElements:
                childElements.append(child)
                num += move_common_attributes_to_parent_group(child, referencedElements)
        elif child.nodeType == Node.TEXT_NODE and child.nodeValue.strip():
            return num

    if len(childElements) <= 1:
        return num

    commonAttrs = {}
    # Seed the intersection with the first child's inheritable attrs.
    # FIXME: if the first child is <set>/<animate*>, its ``fill`` is the
    # animation fill mode, not the presentation property — we should
    # really seed from the first non-animation child.
    attrList = childElements[0].attributes
    for index in range(attrList.length):
        attr = attrList.item(index)
        assert attr is not None
        if attr.nodeName in _INHERITABLE_PROPS:
            commonAttrs[attr.nodeName] = attr.nodeValue or ""

    for childNum in range(len(childElements)):
        if childNum == 0:
            continue

        child = childElements[childNum]
        # Animation elements use ``fill`` for fill mode, not paint —
        # skip them so they don't shrink the intersection incorrectly.
        if child.localName in ["set", "animate", "animateColor", "animateTransform", "animateMotion"]:
            continue

        distinctAttrs = []
        for name in commonAttrs:
            if child.getAttribute(name) != commonAttrs[name]:
                distinctAttrs.append(name)
        for name in distinctAttrs:
            del commonAttrs[name]

    for name in commonAttrs:
        for child in childElements:
            child.removeAttribute(name)
        elem.setAttribute(name, commonAttrs[name])

    num += (len(childElements) - 1) * len(commonAttrs)
    return num


def merge_sibling_groups_with_common_attributes(elem: Element) -> int:
    """Merge consecutive ``<g>`` siblings whose attribute sets match exactly.

    Walks *elem*'s children right-to-left looking for runs of two or
    more adjacent ``<g>`` elements (in the SVG namespace) whose
    attribute dictionaries compare equal. A run can include
    text/comment/whitespace nodes between groups; those nodes are
    appended into the merged group along with the children of the
    later ``<g>``\\(s).

    Every ``<g>`` in the run must pass :func:`g_tag_is_mergeable` —
    otherwise its ``<title>`` / ``<desc>`` would be silently moved
    under a different group's anchor.

    The reverse-iteration loop avoids index invalidation when nodes
    are removed mid-walk. Recurses into every remaining child once
    the merge phase finishes.
    """
    num = 0
    i = elem.childNodes.length - 1
    while i >= 0:
        currentNode = elem.childNodes.item(i)
        assert currentNode is not None
        if (
            currentNode.nodeType != Node.ELEMENT_NODE
            or currentNode.nodeName != "g"
            or currentNode.namespaceURI != NS["SVG"]
        ):
            i -= 1
            continue
        attributes = {a.nodeName: a.nodeValue for a in currentNode.attributes.values()}
        if not attributes:
            i -= 1
            continue
        runStart, runEnd = i, i
        runElements = 1
        while runStart > 0:
            nextNode = elem.childNodes.item(runStart - 1)
            assert nextNode is not None
            if nextNode.nodeType == Node.ELEMENT_NODE:
                if nextNode.nodeName != "g" or nextNode.namespaceURI != NS["SVG"]:
                    break
                nextAttributes = {a.nodeName: a.nodeValue for a in nextNode.attributes.values()}
                if attributes != nextAttributes or not g_tag_is_mergeable(nextNode):
                    break
                runElements += 1
                runStart -= 1
            else:
                runStart -= 1

        i = runStart - 1

        if runElements < 2:
            continue

        # The backward walk above may have stepped past the leftmost
        # <g> into a text/comment node; advance to the actual start.
        while True:
            node = elem.childNodes.item(runStart)
            assert node is not None
            if node.nodeType == Node.ELEMENT_NODE and node.nodeName == "g" and node.namespaceURI == NS["SVG"]:
                break
            runStart += 1
        primaryGroup = elem.childNodes.item(runStart)
        assert primaryGroup is not None
        runStart += 1
        nodes = elem.childNodes[runStart : runEnd + 1]
        for node in nodes:
            if node.nodeType == Node.ELEMENT_NODE and node.nodeName == "g" and node.namespaceURI == NS["SVG"]:
                for child in node.childNodes[:]:
                    primaryGroup.appendChild(child)
                elem.removeChild(node).unlink()
            else:
                primaryGroup.appendChild(node)

    for childNode in elem.childNodes:
        if childNode.nodeType == Node.ELEMENT_NODE:
            num += merge_sibling_groups_with_common_attributes(childNode)

    return num


def create_groups_for_common_attributes(elem: Element, stats: ScourStats) -> None:
    """Wrap runs of 3+ siblings sharing an attribute in a synthetic ``<g>``.

    Sets up the document so a subsequent
    :func:`move_common_attributes_to_parent_group` pass can hoist the
    shared attribute up one level. The attribute is *not* moved here —
    that's the next pass's job.

    For each property in :data:`_INHERITABLE_PROPS`, walks *elem*'s
    children right-to-left and looks for runs of 3+ adjacent elements
    whose value for that property matches. A wrap requires:

    * the children's tag names appear in :data:`_GROUPABLE_CHILDREN`
      (so the new ``<g>`` doesn't violate the SVG content model);
    * the run length is at least 3 elements (smaller runs cost more
      bytes than the synthetic ``<g>`` saves);
    * if the run covers *every* child and *elem* is already a ``<g>``,
      the wrap is skipped — the hoist pass will lift the attribute one
      more level on its own.

    Runs are extended right-to-left to absorb text/comment siblings
    between elements; recurses into every remaining child after each
    property pass.
    """
    for curAttr in _INHERITABLE_PROPS:
        # Iterate in reverse so item(i) for unvisited indices stays
        # stable when we splice nodes out of childNodes.
        curChild = elem.childNodes.length - 1
        while curChild >= 0:
            childNode = elem.childNodes.item(curChild)
            assert childNode is not None

            if (
                childNode.nodeType == Node.ELEMENT_NODE
                and childNode.getAttribute(curAttr)
                and childNode.nodeName in _GROUPABLE_CHILDREN
            ):
                value = childNode.getAttribute(curAttr)
                runStart, runEnd = curChild, curChild
                # runElements counts only element nodes; runLength
                # below counts everything (text, comments, …).
                runElements = 1

                # Extend the run leftwards, allowing whitespace/text
                # nodes between consecutive matching elements.
                while runStart > 0:
                    nextNode = elem.childNodes.item(runStart - 1)
                    assert nextNode is not None
                    if nextNode.nodeType == Node.ELEMENT_NODE:
                        if nextNode.getAttribute(curAttr) != value:
                            break
                        runElements += 1
                        runStart -= 1
                    else:
                        runStart -= 1

                if runElements >= 3:
                    # Pull trailing text/comment siblings into the run
                    # so they're moved with the wrapping <g>.
                    while runEnd < elem.childNodes.length - 1:
                        next_check = elem.childNodes.item(runEnd + 1)
                        assert next_check is not None
                        if next_check.nodeType == Node.ELEMENT_NODE:
                            break
                        runEnd += 1

                    runLength = runEnd - runStart + 1
                    # When all children share the attribute and parent
                    # is already a <g>, skip wrapping and let the hoist
                    # pass lift the attribute one more level. If the
                    # parent is <svg>, fall through and wrap — <svg>
                    # doesn't accept presentation properties like
                    # ``stroke``.
                    if runLength == elem.childNodes.length and elem.nodeName == "g" and elem.namespaceURI == NS["SVG"]:
                        curChild = -1
                        continue

                    document = elem.ownerDocument
                    assert document is not None
                    group = document.createElementNS(NS["SVG"], "g")
                    # Splice the run into the new <g>, then re-parent.
                    group.childNodes[:] = elem.childNodes[runStart : runEnd + 1]
                    for child in group.childNodes:
                        child.parentNode = group
                    elem.childNodes[runStart : runEnd + 1] = []
                    elem.childNodes.insert(runStart, group)
                    group.parentNode = elem
                    curChild = runStart - 1
                    # Net element count went up by one, so reverse the
                    # increment that the caller will apply.
                    stats.num_elements_removed -= 1
                else:
                    curChild -= 1
            else:
                curChild -= 1

    for childNode in elem.childNodes:
        if childNode.nodeType == Node.ELEMENT_NODE:
            create_groups_for_common_attributes(childNode, stats)
