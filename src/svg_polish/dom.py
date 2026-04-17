"""DOM traversal helpers and reference tracking for the SVG optimizer.

These functions never mutate the DOM. They walk a tree and return either
a mapping of element IDs (:func:`find_elements_with_id`) or a mapping of
which IDs are referenced by which nodes (:func:`find_referenced_elements`).
The optimizer pipeline calls them many times per pass — :func:`scour_string`
alone touches :func:`find_referenced_elements` ~8× — so they are written
to be cheap and side-effect free.

The ``url(#id)`` regex helpers (:func:`_replace_url_refs`,
:func:`_build_url_ref_regex`) live here too: they sit on the boundary
between DOM traversal and ID rewriting (used both by ID shortening and by
gradient deduplication), and they own the LRU cache that keeps
pattern-compilation off the hot path.
"""

from __future__ import annotations

import functools
import re
from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.constants import NS, referencingProps
from svg_polish.css import parseCssString
from svg_polish.types import IdentifiedElements, ReferencedIDs

__all__ = [
    "find_elements_with_id",
    "find_referenced_elements",
    "find_referencing_property",
    "_build_url_ref_regex",
    "_replace_url_refs",
    "reset_caches",
]


def find_elements_with_id(node: Element, elems: IdentifiedElements | None = None) -> IdentifiedElements:
    """Return a mapping of ``{id: element}`` for every element with an ``id``.

    Walks *node* and its descendants in document order, recording the first
    element that defines each ID. Duplicate IDs (which the SVG spec forbids
    but inputs may contain) result in the *last* element winning, mirroring
    the historical Scour behaviour.
    """
    if elems is None:
        elems = {}
    elem_id = node.getAttribute("id")
    if elem_id:
        elems[elem_id] = node
    if node.hasChildNodes():
        for child in node.childNodes:
            # See http://www.w3.org/TR/DOM-Level-2-Core/idl-definitions.html —
            # only Element nodes (type 1) carry id attributes.
            if child.nodeType == Node.ELEMENT_NODE:
                find_elements_with_id(child, elems)
    return elems


def find_referenced_elements(node: Element, ids: ReferencedIDs | None = None) -> ReferencedIDs:
    """Return a mapping of ``{id: {referencing_nodes}}`` for every referenced ID.

    Scans ``xlink:href``, CSS ``url(#…)`` references inside ``<style>``
    blocks and inline ``style="…"`` declarations, and every attribute in
    :data:`referencingProps`. The result is the inverse of
    :func:`find_elements_with_id` and is used by the unused-ID and
    unused-defs passes.

    Performance note: ``<style>`` text is parsed lazily via
    :func:`parseCssString` and the result is cached on the node as
    ``_cachedCssRules`` so repeated calls within one optimization run
    don't re-tokenise the stylesheet.
    """
    if ids is None:
        ids = {}

    # Style elements: parse once, cache on the node.
    if node.nodeName == "style" and node.namespaceURI == NS["SVG"]:
        cssRules = getattr(node, "_cachedCssRules", None)
        if cssRules is None:
            # one stretch of text, please! (we could use node.normalize(), but
            # this actually modifies the node, and we don't want to keep
            # whitespace around if there's any)
            stylesheet = "".join(child.nodeValue or "" for child in node.childNodes)
            cssRules = parseCssString(stylesheet) if stylesheet else []
            node._cachedCssRules = cssRules  # type: ignore[attr-defined]
        for rule in cssRules:
            for propname in rule["properties"]:
                propval = rule["properties"][propname]
                find_referencing_property(node, propname, propval, ids)
        return ids

    # xlink:href references — drop the leading '#' and record the binding.
    href = node.getAttributeNS(NS["XLINK"], "href")
    if href and len(href) > 1 and href[0] == "#":
        ref_id = href[1:]
        if ref_id in ids:
            ids[ref_id].add(node)
        else:
            ids[ref_id] = {node}

    # Inline style="…" declarations.
    styles = node.getAttribute("style").split(";")
    for style in styles:
        propval = style.split(":")
        if len(propval) == 2:
            prop = propval[0].strip()
            val = propval[1].strip()
            find_referencing_property(node, prop, val, ids)

    # Direct attributes (fill, stroke, filter, marker, …).
    for attr in referencingProps:
        val = node.getAttribute(attr).strip()
        if not val:
            continue
        find_referencing_property(node, attr, val, ids)

    if node.hasChildNodes():
        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                find_referenced_elements(child, ids)
    return ids


# Precompiled regex matching url(#id), url('#id'), url("#id") at the start
# of an attribute value. Captures the ID itself (group 1).
# A single compiled regex outperforms the multi-branch startswith/find
# chain by ~12% in micro-benchmarks and is more concise than handling all
# three quoting styles manually.
_URL_REF_PROPERTY_RE = re.compile(r"^url\(['\"]?#([^'\")]+)['\"]?\)")


def find_referencing_property(node: Element, prop: str, val: str, ids: ReferencedIDs) -> None:
    """Record *node* in *ids* if *prop*/*val* contains a ``url(#id)`` reference.

    Handles three ``url()`` forms — unquoted, double-quoted, and
    single-quoted — via the single precompiled regex
    :data:`_URL_REF_PROPERTY_RE`.
    """
    if prop not in referencingProps or not val:
        return

    match = _URL_REF_PROPERTY_RE.match(val)
    if match is None:
        return

    ref_id = match.group(1)
    if ref_id in ids:
        ids[ref_id].add(node)
    else:
        ids[ref_id] = {node}


def _replace_url_refs(text: str, id_from: str, id_to: str) -> tuple[str, int]:
    """Replace all ``url(#id_from)`` references in *text* with ``url(#id_to)``.

    Handles three quoting styles: unquoted, single-quoted, double-quoted.
    Uses :func:`re.sub` on a pre-built pattern that matches all three forms
    at once, which is cleaner than three separate ``str.replace()`` calls.

    Args:
        text: The attribute value or CSS text to update.
        id_from: The ID to replace.
        id_to: The replacement ID.

    Returns:
        A tuple of (new_text, replacement_count).
    """
    pattern = _build_url_ref_regex(id_from)
    new_text, count = pattern.subn("url(#" + id_to + ")", text)
    return new_text, count


@functools.lru_cache(maxsize=2048)
def _build_url_ref_regex(elem_id: str) -> re.Pattern[str]:
    """Build a compiled regex matching ``url(#elem_id)`` in all quoting styles.

    Matches ``url(#id)``, ``url('#id')``, and ``url("#id")``. The pattern
    is built from a template with :func:`re.escape` so IDs containing
    regex metacharacters are handled safely.

    The result is cached via :func:`functools.lru_cache` (max 2048 entries)
    — pattern compilation dominates on hot paths like
    :func:`svg_polish.optimizer.rename_id` and
    :func:`svg_polish.optimizer.dedup_gradient`. The bound prevents memory
    growth on adversarial inputs with thousands of unique IDs while still
    covering every realistic SVG.

    Thread-safe in CPython: ``lru_cache`` is implemented in C with internal
    locking, so concurrent calls from multiple threads are race-free.

    Args:
        elem_id: The element ID to match.

    Returns:
        A compiled regex pattern.
    """
    escaped = re.escape(elem_id)
    return re.compile(r"url\(['\"]?#" + escaped + r"['\"]?\)")


def reset_caches() -> None:
    """Clear all module-level caches.

    Intended for tests that need to assert cache behaviour from a clean state
    (e.g. ``cache_info().currsize == 0``). Production code never needs to
    call this — the caches are bounded and thread-safe.
    """
    _build_url_ref_regex.cache_clear()
