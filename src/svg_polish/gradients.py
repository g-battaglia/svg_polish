"""Gradient optimisations: stop dedup, singly-referenced collapse, duplicate removal.

Three independent transforms on ``<linearGradient>`` / ``<radialGradient>``
subtrees. All three are byte-monotonic and idempotent so the optimizer
can run them multiple times until a fixed point.

* :func:`remove_duplicate_gradient_stops` — within one gradient, drop a
  ``<stop>`` that is identical to its immediate predecessor (same offset,
  colour, opacity, style). Also canonicalises the ``offset`` attribute
  to its shortest numeric form.
* :func:`collapse_singly_referenced_gradients` — when gradient *A* is
  referenced by exactly one other gradient *B* via ``xlink:href``, fold
  *A*'s stops and unspecified attributes into *B* and delete *A*. Shortens
  the document by one element and one attribute.
* :func:`remove_duplicate_gradients` — across the whole document, bucket
  gradients by a key that captures every rendering-relevant property
  (type, attributes, stop children, href target). Gradients sharing a
  key are exact visual duplicates; the first is kept as the "master"
  and all references to the others are rewritten to point at it.

:func:`compute_gradient_bucket_key` and :func:`detect_duplicate_gradients`
are helpers exposed so the optimizer orchestrator can drive the
iteration; :func:`dedup_gradient` does the actual reference rewrite
(including ``fill``, ``stroke``, ``xlink:href`` and inline style
declarations). The dedup loop runs until no further duplicates surface,
which is necessary because removing a gradient can reveal fresh
duplicates among the ones that referenced it.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from xml.dom import Node
from xml.dom.minidom import Document, Element

from svg_polish.constants import NS
from svg_polish.dom import find_elements_with_id, find_referenced_elements
from svg_polish.stats import ScourStats
from svg_polish.style import _get_style, _set_style
from svg_polish.types import IdentifiedElements, ReferencedIDs, SVGLength, Unit

__all__ = [
    "collapse_singly_referenced_gradients",
    "compute_gradient_bucket_key",
    "dedup_gradient",
    "detect_duplicate_gradients",
    "remove_duplicate_gradient_stops",
    "remove_duplicate_gradients",
]


def remove_duplicate_gradient_stops(doc: Document, stats: ScourStats) -> int:
    """Drop adjacent duplicate ``<stop>`` children within each gradient.

    For every ``<linearGradient>`` and ``<radialGradient>`` in *doc*,
    walks the ``<stop>`` children in document order and removes any
    stop that matches its immediate predecessor on all of offset,
    ``stop-color``, ``stop-opacity`` and ``style``. Only *consecutive*
    duplicates are removed — non-adjacent identical stops can still
    produce different rendered output via intermediate stops.

    The ``offset`` attribute is canonicalised in the same pass:
    percentages become floats in ``[0, 1]``, and values are rewritten
    to ``int`` when possible (``"50"`` → ``"0.5"`` → ``"0.5"``; but
    ``"0"`` stays ``"0"``) so bucket comparisons later in the pipeline
    don't see false negatives from formatting differences.

    Returns the number of stop elements removed.
    """
    num = 0

    for gradType in ["linearGradient", "radialGradient"]:
        for grad in doc.getElementsByTagName(gradType):
            stops: dict[float | int, list[str]] = {}
            stopsToRemove: list[Element] = []
            for stop in grad.getElementsByTagName("stop"):
                offsetU = SVGLength(stop.getAttribute("offset"))
                if offsetU.units == Unit.PCT:
                    offset = offsetU.value / 100.0
                elif offsetU.units == Unit.NONE:
                    offset = offsetU.value
                else:
                    offset = 0
                # Canonicalise to the shortest string for bucketing.
                if int(offset) == offset:
                    stop.setAttribute("offset", str(int(offset)))
                else:
                    stop.setAttribute("offset", str(offset))

                color = stop.getAttribute("stop-color")
                opacity = stop.getAttribute("stop-opacity")
                style = stop.getAttribute("style")
                if offset in stops:
                    oldStop = stops[offset]
                    if oldStop[0] == color and oldStop[1] == opacity and oldStop[2] == style:
                        stopsToRemove.append(stop)
                stops[offset] = [color, opacity, style]

            for stop in stopsToRemove:
                stop_parent = stop.parentNode
                assert stop_parent is not None
                stop_parent.removeChild(stop)
            num += len(stopsToRemove)
            stats.num_elements_removed += len(stopsToRemove)

    return num


def collapse_singly_referenced_gradients(
    doc: Document,
    stats: ScourStats,
    identifiedElements: IdentifiedElements | None = None,
    referencedIDs: ReferencedIDs | None = None,
) -> int:
    """Fold a gradient into its sole reference and delete the original.

    When a gradient is referenced by exactly one other gradient through
    ``xlink:href``, the referenced gradient is a pure indirection — its
    stops and type-specific attributes (``cx``/``cy``/``r`` for radial,
    ``x1``/``y1``/``x2``/``y2`` for linear) can be copied onto the
    referencing gradient and the original removed.

    The *referencedIDs* map is mutated: ``nodes.pop()`` removes the
    referencing element from the set so a subsequent iteration doesn't
    re-pick the same pair. The caller re-runs this in a loop until it
    returns 0 to catch cascades (A references B references C).

    Args:
        doc: The SVG document.
        stats: Updated with ``num_elements_removed`` for each collapse.
        identifiedElements: Pre-built ``{id: Element}``. If ``None`` the
            function builds it from ``doc.documentElement`` via
            :func:`find_elements_with_id`.
        referencedIDs: Pre-built ``{id: {Element}}``. If ``None`` it is
            built from ``doc.documentElement`` via
            :func:`find_referenced_elements`.

    Returns:
        The number of gradients collapsed in this pass.
    """
    num = 0

    if identifiedElements is None or referencedIDs is None:
        root_doc = doc.documentElement
        assert root_doc is not None
        if identifiedElements is None:
            identifiedElements = find_elements_with_id(root_doc)
        if referencedIDs is None:
            referencedIDs = find_referenced_elements(root_doc)

    for rid, nodes in referencedIDs.items():
        # A document can contain #id references pointing at nothing
        # (Cyn: I've seen documents with #id references but no element with that ID!).
        if len(nodes) == 1 and rid in identifiedElements:
            elem = identifiedElements[rid]
            if (
                elem is not None
                and elem.nodeType == Node.ELEMENT_NODE
                and elem.nodeName in ["linearGradient", "radialGradient"]
                and elem.namespaceURI == NS["SVG"]
            ):
                refElem = nodes.pop()
                if (
                    refElem.nodeType == Node.ELEMENT_NODE
                    and refElem.nodeName in ["linearGradient", "radialGradient"]
                    and refElem.namespaceURI == NS["SVG"]
                ):
                    # elem is a gradient referenced by only one other gradient (refElem).
                    # Move the stops onto refElem only if refElem has none of its own
                    # (otherwise refElem's stops would be incorrectly overridden).
                    if len(refElem.getElementsByTagName("stop")) == 0:
                        stopsToAdd = elem.getElementsByTagName("stop")
                        for stop in stopsToAdd:
                            refElem.appendChild(stop)

                    # Adopt attributes common to both gradient types
                    # only where refElem has no own value.
                    for attr in ["gradientUnits", "spreadMethod", "gradientTransform"]:
                        if refElem.getAttribute(attr) == "" and elem.getAttribute(attr) != "":
                            refElem.setAttributeNS(None, attr, elem.getAttribute(attr))

                    if elem.nodeName == "radialGradient" and refElem.nodeName == "radialGradient":
                        for attr in ["fx", "fy", "cx", "cy", "r"]:
                            if refElem.getAttribute(attr) == "" and elem.getAttribute(attr) != "":
                                refElem.setAttributeNS(None, attr, elem.getAttribute(attr))

                    if elem.nodeName == "linearGradient" and refElem.nodeName == "linearGradient":
                        for attr in ["x1", "y1", "x2", "y2"]:
                            if refElem.getAttribute(attr) == "" and elem.getAttribute(attr) != "":
                                refElem.setAttributeNS(None, attr, elem.getAttribute(attr))

                    target_href = elem.getAttributeNS(NS["XLINK"], "href")
                    if target_href:
                        # elem itself pointed somewhere — refElem now
                        # has to point at that target to preserve the
                        # original paint chain.
                        refElem.setAttributeNS(NS["XLINK"], "href", target_href)
                    else:
                        # elem was a leaf in the chain; refElem no
                        # longer needs an xlink:href at all.
                        refElem.removeAttributeNS(NS["XLINK"], "href")

                    elem_parent = elem.parentNode
                    assert elem_parent is not None
                    elem_parent.removeChild(elem)
                    stats.num_elements_removed += 1
                    num += 1

    return num


def compute_gradient_bucket_key(grad: Element) -> str:
    """Return a string key such that identical keys mean identical gradients.

    Captures every rendering-relevant property: gradient type attrs
    (``gradientUnits``, ``spreadMethod``, ``gradientTransform``, plus
    the type-specific geometry), the xlink:href target, and every
    ``<stop>`` child's offset/colour/opacity/style. The parts are
    joined with ``\\x1e`` (ASCII record separator) — chosen because
    it cannot appear in a valid SVG attribute value, so it can't
    produce a false positive through string collision.

    A ``linearGradient`` and a ``radialGradient`` never collide: the
    type-specific geometry attributes (``x1``/``y1`` vs ``fx``/``fy``)
    are all read and distinguish them.
    """
    gradBucketAttr = [
        "gradientUnits",
        "spreadMethod",
        "gradientTransform",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "fx",
        "fy",
        "r",
    ]
    gradStopBucketsAttr = ["offset", "stop-color", "stop-opacity", "style"]

    subKeys = [grad.getAttribute(a) for a in gradBucketAttr]
    subKeys.append(grad.getAttributeNS(NS["XLINK"], "href"))
    stops = grad.getElementsByTagName("stop")
    if stops.length:
        for i in range(stops.length):
            stop = stops.item(i)
            assert stop is not None
            for attr in gradStopBucketsAttr:
                stopKey = stop.getAttribute(attr)
                subKeys.append(stopKey)

    # \x1e = ASCII record separator: not valid in SVG attribute
    # values, so concatenation is collision-free without escaping.
    return "\x1e".join(subKeys)


def detect_duplicate_gradients(
    *grad_lists: Iterable[Element],
) -> Iterator[tuple[str, list[str], list[Element]]]:
    """Yield groups of duplicate gradients across the given iterables.

    For each iterable argument (typically the linear and radial
    gradient lists), builds a bucket from
    :func:`compute_gradient_bucket_key` and yields one tuple per
    bucket that contains 2+ gradients:

    ``(master_id, duplicates_ids, duplicates)``

    where *master* is the first gradient in the bucket and
    *duplicates* are the rest. The master is always the one whose ID
    will win — if the first gradient lacks an ID but a later one has
    one, the function swaps them so *master_id* is always non-empty
    when *any* gradient in the bucket has an ID (see GH#203 — without
    this swap, all references to the duplicates would become dangling
    because the master has no ID to point at).
    """
    for grads in grad_lists:
        grad_buckets = defaultdict(list)

        for grad in grads:
            key = compute_gradient_bucket_key(grad)
            grad_buckets[key].append(grad)

        for bucket in grad_buckets.values():
            if len(bucket) < 2:
                continue
            master = bucket[0]
            duplicates = bucket[1:]
            duplicates_ids = [d.getAttribute("id") for d in duplicates]
            master_id = master.getAttribute("id")
            if not master_id:
                # Borrow an ID from a duplicate so references can
                # survive the collapse. The old "master" (no ID) is
                # relegated to a duplicate — losing it is harmless
                # because nothing could reference it anyway.
                for i in range(len(duplicates_ids)):
                    dup_id = duplicates_ids[i]
                    if dup_id:
                        master_id = duplicates_ids[i]
                        duplicates[i] = master
                        # Clear the borrowed ID so it isn't also
                        # remapped below.
                        duplicates_ids[i] = ""
                        break

            yield master_id, duplicates_ids, duplicates


def dedup_gradient(
    master_id: str,
    duplicates_ids: list[str],
    duplicates: list[Element],
    referenced_ids: ReferencedIDs,
) -> None:
    """Rewrite all references to *duplicates* onto *master_id* and unlink them.

    Walks every (dup_id, dup_element) pair and:

    1. Skips duplicates that no longer have a parent (already
       remapped in an earlier pass).
    2. Rewrites ``fill``, ``stroke``, ``xlink:href`` and inline style
       ``url(#dup_id)`` references on each element that the
       *referenced_ids* map says points at this duplicate, pointing
       them at *master_id* instead.
    3. Removes the duplicate element from the DOM.

    Uses a single combined regex for all duplicate IDs — building one
    pattern per ID would be O(N·M) with N duplicates and M
    references; the combined pattern is O(N+M). The pattern is built
    lazily only when at least one duplicate is actually referenced.

    Updates *referenced_ids* to fold the duplicates' reference sets
    into the master's entry so the caller can iterate more than once
    without rebuilding the whole reference map (one of the hottest
    operations in the pipeline).
    """
    # One combined regex avoids the per-ID build cost that rename_id
    # pays through its lru_cache; dedup_gradient runs over a different
    # ID set each call, so caching wouldn't help here.
    func_iri = None
    for dup_id, dup_grad in zip(duplicates_ids, duplicates, strict=True):
        if not dup_grad.parentNode:
            continue

        # ``--keep-unreferenced-defs`` can leave a duplicate that
        # nothing references — skip the rewrite and just delete it (GH#156).
        if dup_id in referenced_ids:
            if func_iri is None:
                # Matches url(#X), url('#X') and url("#X") for any X
                # in the duplicate set.
                dup_id_regex = "|".join(duplicates_ids)
                func_iri = re.compile("url\\(['\"]?#(?:" + dup_id_regex + ")['\"]?\\)")
            for elem in referenced_ids[dup_id]:
                for attr in ["fill", "stroke"]:
                    v = elem.getAttribute(attr)
                    (v_new, n) = func_iri.subn("url(#" + master_id + ")", v)
                    if n > 0:
                        elem.setAttribute(attr, v_new)
                if elem.getAttributeNS(NS["XLINK"], "href") == "#" + dup_id:
                    elem.setAttributeNS(NS["XLINK"], "href", "#" + master_id)
                styles = _get_style(elem)
                for style in styles:
                    v = styles[style]
                    (v_new, n) = func_iri.subn("url(#" + master_id + ")", v)
                    if n > 0:
                        styles[style] = v_new
                _set_style(elem, styles)

        dup_grad.parentNode.removeChild(dup_grad)

    # Fold the duplicates' reference sets into the master's so the
    # caller can run dedup in a while-loop without rebuilding the full
    # reference map — find_referenced_elements is one of the slowest
    # functions in the pipeline.
    if master_id:
        try:
            master_references = referenced_ids[master_id]
        except KeyError:
            master_references = set()

        for dup_id in duplicates_ids:
            references = referenced_ids.pop(dup_id, None)
            if references is None:
                continue
            master_references.update(references)

        referenced_ids[master_id] = master_references


def remove_duplicate_gradients(doc: Document, referencedIDs: ReferencedIDs | None = None) -> int:
    """Remove exact-duplicate gradients document-wide, rewriting references.

    Iterates in a fixed-point loop: each pass detects duplicate
    buckets via :func:`detect_duplicate_gradients` and rewrites them
    via :func:`dedup_gradient`. Removing a gradient can reveal fresh
    duplicates among the ones that referenced it (A→B and C→D; if B
    and D are now identical duplicates, the loop catches them on the
    next pass).

    Args:
        doc: The SVG document.
        referencedIDs: Pre-built ``{id: {Element}}``. If ``None`` the
            function builds one from ``doc.documentElement`` via
            :func:`find_referenced_elements`.

    Returns:
        The total number of duplicate gradients removed across all
        iterations.
    """
    prev_num = -1
    num = 0

    if referencedIDs is None:
        root_for_refs = doc.documentElement
        assert root_for_refs is not None
        referenced_ids = find_referenced_elements(root_for_refs)
    else:
        referenced_ids = referencedIDs

    while prev_num != num:
        prev_num = num

        linear_gradients = doc.getElementsByTagName("linearGradient")
        radial_gradients = doc.getElementsByTagName("radialGradient")

        for master_id, duplicates_ids, duplicates in detect_duplicate_gradients(linear_gradients, radial_gradients):
            dedup_gradient(master_id, duplicates_ids, duplicates, referenced_ids)
            num += len(duplicates)

    return num
