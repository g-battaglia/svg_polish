"""ID management: shortening, renaming, protection, unused-defs cleanup.

The optimizer collapses long, designer-assigned IDs (``MyAwesomeIcon``)
into the shortest spreadsheet-style names possible (``a``, ``b``, …, ``aa``)
and prunes unreferenced ones. This module owns that whole flow:

* :func:`shorten_ids` is the orchestrator — picks the optimal length
  schedule and walks the document.
* :func:`compute_id_lengths` and :func:`int_to_id` produce the
  spreadsheet-style names.
* :func:`rename_id` rewrites every reference (xlink:href, ``url(#id)`` in
  attributes, inline styles and ``<style>`` blocks).
* :func:`protected_ids` / :func:`unprotected_ids` honour the user's
  ``--protect-ids-*`` flags.
* :func:`remove_unused_defs` and :func:`remove_unreferenced_elements`
  strip orphan ``<defs>`` children and unreferenced gradients/patterns.

Functions mutate the DOM in place (where they have to) and return integer
counts that the pipeline accumulates into :class:`ScourStats`.
"""

from __future__ import annotations

import optparse
from collections.abc import Iterator
from xml.dom import Node
from xml.dom.minidom import Document, Element

from svg_polish.constants import NS, referencingProps
from svg_polish.dom import _build_url_ref_regex, find_elements_with_id, find_referenced_elements
from svg_polish.stats import ScourStats
from svg_polish.style import _invalidate_style_cache
from svg_polish.types import IdentifiedElements, ReferencedIDs

__all__ = [
    "compute_id_lengths",
    "int_to_id",
    "protected_ids",
    "remove_unreferenced_elements",
    "remove_unreferenced_ids",
    "remove_unused_defs",
    "rename_id",
    "shorten_ids",
    "unprotected_ids",
]


# =============================================================================
# Unused element removal
# =============================================================================


def remove_unused_defs(
    doc: Document,
    defElem: Element,
    elemsToRemove: list[Element] | None = None,
    referencedIDs: ReferencedIDs | None = None,
) -> list[Element]:
    """Collect elements inside *defElem* that are not referenced anywhere in *doc*.

    Recursive: groups inside ``<defs>`` are descended into when the group
    itself is unreferenced. Tags listed in ``keepTags`` (font, style,
    metadata, script, title, desc) are always preserved regardless of
    references — they carry semantics that can be hard to reason about.
    """
    if elemsToRemove is None:
        elemsToRemove = []

    # remove_unused_defs does not change the XML itself; therefore there is
    # no point in recomputing find_referenced_elements when we recurse.
    if referencedIDs is None:
        root = doc.documentElement
        assert root is not None
        referencedIDs = find_referenced_elements(root)

    keepTags = ["font", "style", "metadata", "script", "title", "desc"]
    for elem in defElem.childNodes:
        if elem.nodeType != Node.ELEMENT_NODE:
            continue

        elem_id = elem.getAttribute("id")

        if elem_id == "" or elem_id not in referencedIDs:
            # we only inspect the children of a group in a defs if the group
            # is not referenced anywhere else
            if elem.nodeName == "g" and elem.namespaceURI == NS["SVG"]:
                elemsToRemove = remove_unused_defs(doc, elem, elemsToRemove, referencedIDs=referencedIDs)
            elif elem.nodeName not in keepTags:
                elemsToRemove.append(elem)
    return elemsToRemove


def remove_unreferenced_elements(
    doc: Document,
    keepDefs: bool,
    stats: ScourStats,
    identifiedElements: IdentifiedElements | None = None,
    referencedIDs: ReferencedIDs | None = None,
) -> int:
    """Remove unreferenced gradients/patterns outside ``<defs>`` and unused defs children.

    Two phases:
        1. Sweep ``<defs>`` and drop unreferenced children (unless
           ``keepDefs`` is set).
        2. Walk every identified element; remove the linearGradient,
           radialGradient or pattern nodes that no one references and that
           live outside ``<defs>`` (gradients inside ``<defs>`` were
           already handled in phase 1).
    """
    num = 0

    removeTags = ["linearGradient", "radialGradient", "pattern"]
    root = doc.documentElement
    assert root is not None
    if identifiedElements is None:
        identifiedElements = find_elements_with_id(root)
    if referencedIDs is None:
        referencedIDs = find_referenced_elements(root)

    if not keepDefs:
        defs = root.getElementsByTagName("defs")
        for aDef in defs:
            elemsToRemove = remove_unused_defs(doc, aDef, referencedIDs=referencedIDs)
            for elem in elemsToRemove:
                parent = elem.parentNode
                assert parent is not None
                parent.removeChild(elem)
            stats.num_elements_removed += len(elemsToRemove)
            num += len(elemsToRemove)

    for elem_id, elem in identifiedElements.items():
        if elem_id not in referencedIDs:
            goner = elem
            goner_parent = goner.parentNode if goner is not None else None
            if (
                goner is not None
                and goner.nodeName in removeTags
                and goner_parent is not None
                and getattr(goner_parent, "tagName", None) != "defs"
            ):
                goner_parent.removeChild(goner)
                num += 1
                stats.num_elements_removed += 1

    return num


# =============================================================================
# ID Management (shortening, renaming, protection)
# =============================================================================


def shorten_ids(
    doc: Document,
    prefix: str,
    options: optparse.Values,
    identifiedElements: IdentifiedElements | None = None,
    referencedIDs: ReferencedIDs | None = None,
) -> int:
    """Shorten ID names so the most-referenced IDs get the shortest names.

    The algorithm is:

    1. Sort IDs by reference count (descending) so popular IDs win the
       short names.
    2. Compute how many IDs of each length are available
       (:func:`compute_id_lengths`).
    3. For each ID, either keep it (if already optimal length) or queue it
       for renaming.
    4. Walk the rename queue and assign the next available short ID via
       :func:`int_to_id`, skipping protected and already-consumed names.

    Returns the total number of bytes saved across all rewrites.
    """
    num = 0

    if identifiedElements is None or referencedIDs is None:
        root_doc = doc.documentElement
        assert root_doc is not None
        if identifiedElements is None:
            identifiedElements = find_elements_with_id(root_doc)
        # Maps original ID → set of nodes referencing it. After this
        # function runs the map is no longer valid; we don't reuse it
        # downstream so we don't bother keeping it consistent.
        if referencedIDs is None:
            referencedIDs = find_referenced_elements(root_doc)

    # Order IDs by reference count descending. Filter out IDs referenced
    # but never defined (Cyn: "I've seen documents with #id references
    # but no element with that ID!").
    idCounts: list[tuple[int, str]] = [
        (len(referencedIDs[rid]), rid) for rid in referencedIDs if rid in identifiedElements
    ]
    idCounts.sort(reverse=True)
    idList: list[str] = [rid for count, rid in idCounts]

    # Append unreferenced IDs at the end (arbitrary order).
    idList.extend([rid for rid in identifiedElements if rid not in idList])
    # Avoid colliding with protected IDs.
    protectedIDs = protected_ids(identifiedElements, options)
    consumedIDs = set()

    # IDs scheduled for a new (possibly longer) name. Order matters:
    # earlier entries get shorter names.
    need_new_id = []

    id_allocations = list(compute_id_lengths(len(idList) + 1))
    # Reverse so we can use it as a stack and still work shortest-to-longest.
    id_allocations.reverse()

    optimal_id_length, id_use_limit = 0, 0
    for current_id in idList:
        if id_use_limit < 1:
            optimal_id_length, id_use_limit = id_allocations.pop()
        id_use_limit -= 1
        # Strict equality: even shorter IDs may need to grow because a
        # higher-priority ID grabbed the optimal length.
        if len(current_id) == optimal_id_length:
            consumedIDs.add(current_id)
        else:
            need_new_id.append(current_id)

    curIdNum = 1

    for old_id in need_new_id:
        new_id = int_to_id(curIdNum, prefix)

        # Skip protected or already-consumed names.
        while new_id in protectedIDs or new_id in consumedIDs:
            curIdNum += 1
            new_id = int_to_id(curIdNum, prefix)

        num += rename_id(old_id, new_id, identifiedElements, referencedIDs.get(old_id))
        curIdNum += 1

    return num


def compute_id_lengths(highest: int) -> Iterator[tuple[int, int]]:
    """Compute how many IDs are available at each name length.

    Example:
        >>> lengths = list(compute_id_lengths(512))
        >>> lengths
        [(1, 26), (2, 676)]
        >>> total_limit = sum(x[1] for x in lengths)
        >>> total_limit
        702
        >>> int_to_id(total_limit, '')
        'zz'

    Which tells us we have 26 IDs of length 1 and up to 676 IDs of length 2
    if we need to allocate 512 IDs.

    :param highest: Highest ID number that needs to be allocated.
    :return: Iterator of (id-length, use-limit) tuples. ``use_limit``
        applies only to that length (excluding shorter ones). The sum of
        all ``use_limit`` values is always ≥ ``highest``.
    """
    step = 26
    id_length = 0
    use_limit = 1
    while highest:
        id_length += 1
        use_limit *= step
        yield (id_length, use_limit)
        highest = int((highest - 1) / step)


def int_to_id(idnum: int, prefix: str) -> str:
    """Return a spreadsheet-style ID name for *idnum*.

    a, b, …, z, then aa, ab, …, az, ba, …, zz, then aaa, … and so on.
    """
    rid = ""
    while idnum > 0:
        idnum -= 1
        rid = chr((idnum % 26) + ord("a")) + rid
        idnum = int(idnum / 26)
    return prefix + rid


def rename_id(
    idFrom: str,
    idTo: str,
    identifiedElements: IdentifiedElements,
    referringNodes: set[Element] | None,
) -> int:
    """Rename the element with id *idFrom* to *idTo* and update every reference.

    Returns the number of bytes saved across the defining attribute and
    all rewritten references.
    """
    num_bytes_saved = 0

    defining_node = identifiedElements[idFrom]
    defining_node.setAttribute("id", idTo)
    num_bytes_saved += len(idFrom) - len(idTo)

    if referringNodes is not None:
        # Build the URL replacement regex once for all referencing nodes.
        url_pattern = _build_url_ref_regex(idFrom)
        replacement = "url(#" + idTo + ")"

        for node in referringNodes:
            # ``<style>`` element: rewrite the CSS text wholesale.
            if node.nodeName == "style" and node.namespaceURI == NS["SVG"] and node.firstChild is not None:
                # Concatenate every child node's value so CDATASections
                # surrounded by whitespace are preserved.
                # (node.normalize() is text-only and would not work.)
                old_value = "".join(child.nodeValue or "" for child in node.childNodes)
                new_value, _ = url_pattern.subn(replacement, old_value)
                owner_doc = node.ownerDocument
                assert owner_doc is not None
                node.childNodes[:] = [owner_doc.createTextNode(new_value)]
                num_bytes_saved += len(old_value) - len(new_value)

            # xlink:href="#idFrom" → xlink:href="#idTo".
            href = node.getAttributeNS(NS["XLINK"], "href")
            if href == "#" + idFrom:
                node.setAttributeNS(NS["XLINK"], "href", "#" + idTo)
                num_bytes_saved += len(idFrom) - len(idTo)

            # Inline style="…": rewrite via the cached regex.
            styles = node.getAttribute("style")
            if styles:
                new_value, _ = url_pattern.subn(replacement, styles)
                node.setAttribute("style", new_value)
                _invalidate_style_cache(node)
                num_bytes_saved += len(styles) - len(new_value)

            # fill, stroke, filter, marker, … attributes.
            for attr in referencingProps:
                old_value = node.getAttribute(attr)
                if old_value:
                    new_value, _ = url_pattern.subn(replacement, old_value)
                    node.setAttribute(attr, new_value)
                    num_bytes_saved += len(old_value) - len(new_value)

    return num_bytes_saved


def protected_ids(seenIDs: IdentifiedElements, options: optparse.Values) -> list[str]:
    """Return the IDs in *seenIDs* matched by any ``--protect-ids-*`` option.

    The result is the set of names the shortener must not reuse.
    """
    protectedIDs = []
    if options.protect_ids_prefix or options.protect_ids_noninkscape or options.protect_ids_list:
        protect_ids_prefixes = []
        protect_ids_list = []
        if options.protect_ids_list:
            protect_ids_list = options.protect_ids_list.split(",")
        if options.protect_ids_prefix:
            protect_ids_prefixes = options.protect_ids_prefix.split(",")
        for elem_id in seenIDs:
            non_inkscape_match = options.protect_ids_noninkscape and not elem_id[-1].isdigit()
            in_explicit_list = protect_ids_list and elem_id in protect_ids_list
            prefix_match = protect_ids_prefixes and any(elem_id.startswith(prefix) for prefix in protect_ids_prefixes)
            if non_inkscape_match or in_explicit_list or prefix_match:
                protectedIDs.append(elem_id)
    return protectedIDs


def unprotected_ids(doc: Document, options: optparse.Values) -> IdentifiedElements:
    """Return identified elements with the protected IDs removed."""
    root = doc.documentElement
    assert root is not None
    identifiedElements = find_elements_with_id(root)
    protectedIDs = protected_ids(identifiedElements, options)
    if protectedIDs:
        for protected_id in protectedIDs:
            del identifiedElements[protected_id]
    return identifiedElements


def remove_unreferenced_ids(referencedIDs: ReferencedIDs, identifiedElements: IdentifiedElements) -> int:
    """Strip ``id`` attributes that are never referenced.

    ``<font>`` elements keep their IDs unconditionally — the SVG fonts
    spec uses them as glyph anchors regardless of explicit references.

    Returns the number of ID attributes removed.
    """
    keepTags = ["font"]
    num = 0
    for elem_id, node in identifiedElements.items():
        if elem_id not in referencedIDs and node.nodeName not in keepTags:
            node.removeAttribute("id")
            num += 1
    return num
