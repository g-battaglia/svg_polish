"""XML namespace pruning and prefix remapping.

The optimizer uses these helpers to strip editor-private attributes
(Inkscape, Sodipodi, Adobe Illustrator, Sketch) and to canonicalise the
namespace-prefix layout of the output document. They mutate the DOM in
place and return integer counts for the :class:`ScourStats` aggregator.

Functions here are pure DOM walks — they hold no module-level state and
only depend on :mod:`xml.dom`.
"""

from __future__ import annotations

from xml.dom import Node
from xml.dom.minidom import Element

__all__ = [
    "remap_namespace_prefix",
    "remove_namespaced_attributes",
    "remove_namespaced_elements",
]


def remove_namespaced_attributes(node: Element, namespaces: list[str]) -> int:
    """Remove every attribute whose namespace URI is in *namespaces*.

    Walks *node* and its descendants. Non-Element nodes can never carry
    namespaced attributes, so the recursion is gated on ``nodeType``. The
    function is annotated as taking :class:`Element` for its primary call
    sites; the recursion passes child nodes (any of
    ``Element|Comment|Text|...``) which are filtered by the ``nodeType``
    guard at the top.

    Returns the number of attributes removed across the whole subtree.
    """
    num = 0
    if node.nodeType == Node.ELEMENT_NODE:
        attrList = node.attributes
        attrsToRemove: list[str] = []
        for attrNum in range(attrList.length):
            attr = attrList.item(attrNum)
            if attr is not None and attr.namespaceURI in namespaces and attr.nodeName is not None:
                attrsToRemove.append(attr.nodeName)
        for attrName in attrsToRemove:
            node.removeAttribute(attrName)
        num += len(attrsToRemove)

        for child in node.childNodes:
            num += remove_namespaced_attributes(child, namespaces)  # type: ignore[arg-type]
    return num


def remove_namespaced_elements(node: Element, namespaces: list[str]) -> int:
    """Remove every child element whose namespace URI is in *namespaces*.

    Recursive walk; the same ``nodeType`` guard rationale as
    :func:`remove_namespaced_attributes` applies. Returns the number of
    elements removed across the subtree.
    """
    num = 0
    if node.nodeType == Node.ELEMENT_NODE:
        childList = node.childNodes
        childrenToRemove = []
        for child in childList:
            if child is not None and child.namespaceURI in namespaces:
                childrenToRemove.append(child)
        for child in childrenToRemove:
            node.removeChild(child)
        num += len(childrenToRemove)

        for child in node.childNodes:
            num += remove_namespaced_elements(child, namespaces)  # type: ignore[arg-type]
    return num


def remap_namespace_prefix(node: Element, oldprefix: str, newprefix: str) -> None:
    """Recursively rename namespace prefix *oldprefix* to *newprefix* in the subtree.

    Used by the SVG-namespace canonicalisation step at the end of the
    pipeline: any element still tagged with the historical default-SVG
    prefix (``svg:rect``) is rewritten to the un-prefixed form
    (``rect``) so the output matches the canonical SVG serialization.

    The DOM API does not allow editing a node's prefix in place, so each
    matching element is replaced by a freshly-constructed copy with the
    same attributes and child clones.
    """
    if node is None or node.nodeType != Node.ELEMENT_NODE:
        return

    if node.prefix == oldprefix:
        localName = node.localName
        namespace = node.namespaceURI
        doc = node.ownerDocument
        parent = node.parentNode
        assert doc is not None
        assert parent is not None

        # Create a replacement node with the new prefix (or unprefixed).
        if newprefix != "":  # pragma: no cover — always called with newprefix=""
            newNode = doc.createElementNS(namespace, newprefix + ":" + localName)
        else:
            newNode = doc.createElement(localName)

        # Copy attributes verbatim, preserving namespace bindings.
        attrList = node.attributes
        for i in range(attrList.length):
            attr = attrList.item(i)
            assert attr is not None
            newNode.setAttributeNS(attr.namespaceURI, attr.name, attr.nodeValue or "")  # type: ignore[attr-defined]

        # Deep-clone all children so the original subtree isn't disturbed.
        for child in node.childNodes:
            newNode.appendChild(child.cloneNode(True))  # type: ignore[type-var]

        parent.replaceChild(newNode, node)
        node = newNode

    for child in node.childNodes:
        remap_namespace_prefix(child, oldprefix, newprefix)  # type: ignore[arg-type]
