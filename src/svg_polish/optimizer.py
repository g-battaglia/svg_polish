"""SVG optimization orchestrator.

This module wires the optimization pipeline together. The actual passes
(path / transform / length / colors / groups / gradients / ids / …) live in
their own single-purpose modules under :mod:`svg_polish.passes` and the
top-level helper packages (:mod:`svg_polish.dom`, :mod:`svg_polish.style`,
etc.). The CLI parser, file-I/O helpers, and console script entry point
live in :mod:`svg_polish.cli`.

Public entry point: :func:`scour_string`. :func:`scour_xml_file` is a
convenience wrapper that reads from disk.

Originally from Scour (https://github.com/scour-project/scour).

Original copyright:
    Copyright 2010 Jeff Schiller
    Copyright 2010 Louis Simard
    Copyright 2013-2014 Tavendo GmbH

Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import optparse
import sys
import warnings
import xml.dom.minidom
from typing import TYPE_CHECKING
from xml.dom import Node, NotFoundErr
from xml.parsers.expat import ExpatError

import defusedxml.minidom
from defusedxml import EntitiesForbidden, ExternalReferenceForbidden, NotSupportedError

from svg_polish.colors import (
    convert_color,  # noqa: F401 — re-exported for tests
    convert_colors,
)
from svg_polish.constants import (
    RE_COMMA_WSP,
    XML_ENTS_ESCAPE_APOS,  # noqa: F401 — re-exported for tests
    XML_ENTS_ESCAPE_QUOT,  # noqa: F401 — re-exported for tests
    unwanted_ns,
)
from svg_polish.dom import (
    _build_url_ref_regex,  # noqa: F401 — re-exported for tests
    _replace_url_refs,  # noqa: F401 — re-exported for tests
    find_elements_with_id,  # noqa: F401 — re-exported for tests
    find_referenced_elements,
    reset_caches,  # noqa: F401 — re-exported for tests
)
from svg_polish.exceptions import SvgParseError, SvgSecurityError
from svg_polish.gradients import (
    collapse_singly_referenced_gradients,
    compute_gradient_bucket_key,  # noqa: F401 — re-exported for tests
    dedup_gradient,  # noqa: F401 — re-exported for tests
    detect_duplicate_gradients,  # noqa: F401 — re-exported for tests
    remove_duplicate_gradient_stops,
    remove_duplicate_gradients,
)
from svg_polish.groups import (
    create_groups_for_common_attributes,
    g_tag_is_mergeable,  # noqa: F401 — re-exported for tests
    merge_sibling_groups_with_common_attributes,
    move_common_attributes_to_parent_group,
    remove_nested_groups,
)
from svg_polish.ids import (
    remove_unreferenced_elements,
    remove_unreferenced_ids,
    remove_unused_defs,  # noqa: F401 — re-exported for tests
    rename_id,  # noqa: F401 — re-exported for tests
    shorten_ids,
    unprotected_ids,
)
from svg_polish.namespaces import (
    remap_namespace_prefix,
    remove_namespaced_attributes,
    remove_namespaced_elements,
)
from svg_polish.options import DEFAULT_MAX_INPUT_BYTES, OptimizeOptions
from svg_polish.passes.attributes import remove_unused_attributes_on_parent
from svg_polish.passes.comments import remove_comments
from svg_polish.passes.defaults import (
    _iter_attr_names,  # noqa: F401 — re-exported for tests
    remove_default_attribute_value,  # noqa: F401 — re-exported for tests
    remove_default_attribute_values,
    taint,  # noqa: F401 — re-exported for tests
)
from svg_polish.passes.length import (
    reduce_precision,
    scour_length,
    scour_unitless_length,
)
from svg_polish.passes.path import (
    clean_path,
    clean_polygon,
    clean_polyline,
    control_points,  # noqa: F401 — re-exported for tests
    flags,  # noqa: F401 — re-exported for tests
    is_same_direction,  # noqa: F401 — re-exported for tests
    is_same_sign,  # noqa: F401 — re-exported for tests
    parse_list_of_points,  # noqa: F401 — re-exported for tests
    scour_coordinates,  # noqa: F401 — re-exported for tests
    serialize_path,  # noqa: F401 — re-exported for tests
)
from svg_polish.passes.rasters import embed_rasters
from svg_polish.passes.sizing import properly_size_doc
from svg_polish.passes.transform import (
    optimize_angle,  # noqa: F401 — re-exported for tests
    optimize_transform,  # noqa: F401 — re-exported for tests
    optimize_transforms,
    serialize_transform,  # noqa: F401 — re-exported for tests
)
from svg_polish.serialize import (
    make_well_formed,  # noqa: F401 — re-exported for tests
    serialize_xml,
)
from svg_polish.stats import ScourStats
from svg_polish.style import (
    may_contain_text_nodes,  # noqa: F401 — re-exported for tests
    repair_style,
    style_inherited_by_child,  # noqa: F401 — re-exported for tests
    style_inherited_from_parent,  # noqa: F401 — re-exported for tests
)
from svg_polish.types import (
    DecimalEngine,
    Unit,  # noqa: F401 — re-exported for tests
    precision_scope,
)

if TYPE_CHECKING:
    from xml.dom.minidom import Document, Element


# =============================================================================
# XML and SVG Namespace Constants
# =============================================================================


# =============================================================================
# SVG Presentation Attributes
# =============================================================================
# (Imported from svg_polish.constants)


# =============================================================================
# Named CSS Colors
# =============================================================================
# (Imported from svg_polish.constants)


# =============================================================================
# CSS/SVG Default Property Values
# =============================================================================
# (Imported from svg_polish.constants)


# =============================================================================
# Secure XML Parsing
# =============================================================================


class SecurityWarning(UserWarning):
    """Warning emitted when ``allow_xml_entities`` disables defusedxml hardening."""


# Default ceiling for input size (100 MiB). Re-exported for backwards
# compatibility with tests that imported the symbol from this module before
# Sprint 3 consolidated it into :mod:`svg_polish.options`.
_DEFAULT_MAX_INPUT_BYTES = DEFAULT_MAX_INPUT_BYTES


def _measure_input_bytes(in_string: str | bytes) -> int:
    """Return the byte length of *in_string* without forcing a Unicode encode.

    For bytes inputs this is just ``len(in_string)``. For str we use the UTF-8
    byte count, which matches what the parser will actually allocate.
    """
    if isinstance(in_string, bytes):
        return len(in_string)
    # Encoding once is cheap relative to parsing; we throw the result away.
    return len(in_string.encode("utf-8"))


def _parse_xml(in_string: str | bytes, options: optparse.Values | None) -> "Document":
    """Parse *in_string* into a minidom ``Document`` with secure-by-default behavior.

    Security checks (in order):

    1. **Size limit** — input larger than ``options.max_input_bytes``
       (default :data:`_DEFAULT_MAX_INPUT_BYTES`) is rejected with
       :class:`SvgSecurityError` *before* the parser runs. ``None`` disables
       the limit.
    2. **Entity expansion** — uses ``defusedxml.minidom.parseString`` which
       refuses DOCTYPE entity definitions and external references (XXE,
       billion-laughs). Triggers raise :class:`SvgSecurityError`.
    3. **Permissive opt-out** — if ``options.allow_xml_entities`` is True,
       parsing falls back to the standard library parser and a
       :class:`SecurityWarning` is emitted. Use only for trusted input.

    Raw ``xml.parsers.expat.ExpatError`` is wrapped in :class:`SvgParseError`
    with line/column/snippet attributes populated. The snippet is truncated
    to 80 chars by :class:`SvgParseError` so we never leak large input.
    """
    max_bytes = getattr(options, "max_input_bytes", _DEFAULT_MAX_INPUT_BYTES)
    # Accept -1 (CLI sentinel) or None as "no limit". Any positive integer
    # caps the input size before the parser runs.
    if max_bytes is not None and max_bytes >= 0:
        size = _measure_input_bytes(in_string)
        if size > max_bytes:
            raise SvgSecurityError(f"input is {size} bytes, exceeds max_input_bytes={max_bytes}")

    allow_entities = bool(getattr(options, "allow_xml_entities", False))
    try:
        if allow_entities:
            warnings.warn(
                "XML entities allowed: input must be trusted",
                category=SecurityWarning,
                stacklevel=3,
            )
            return xml.dom.minidom.parseString(in_string)
        # defusedxml's stub types parseString as accepting only ``str``, but
        # the runtime delegates to ``xml.dom.minidom.parseString`` which also
        # accepts ``bytes`` — required so we can let expat detect the input
        # encoding from the XML prolog (e.g. ISO-8859-15 fixtures).
        return defusedxml.minidom.parseString(in_string)  # type: ignore[arg-type]
    except (EntitiesForbidden, ExternalReferenceForbidden, NotSupportedError) as exc:
        raise SvgSecurityError("input rejected: contains forbidden XML entity or external reference") from exc
    except ExpatError as exc:
        # decode(errors="replace") never raises, so a bytes input always yields
        # a snippet candidate — SvgParseError truncates it to 80 chars.
        snippet = in_string.decode("utf-8", errors="replace") if isinstance(in_string, bytes) else in_string
        raise SvgParseError(
            f"failed to parse SVG/XML: {exc}",
            line=getattr(exc, "lineno", None),
            column=getattr(exc, "offset", None),
            snippet=snippet,
        ) from exc


# =============================================================================
# Length Parsing (Unit, SVGLength)
# =============================================================================
# (Imported from svg_polish.types)


# =============================================================================
# Descriptive Element Removal
# =============================================================================


def remove_descriptive_elements(doc: Document, options: optparse.Values) -> int:
    """Remove ``<title>``, ``<desc>``, and ``<metadata>`` elements when requested by options."""
    elementTypes: list[str] = []
    if options.remove_descriptive_elements:
        elementTypes.extend(("title", "desc", "metadata"))
    else:
        if options.remove_titles:
            elementTypes.append("title")
        if options.remove_descriptions:
            elementTypes.append("desc")
        if options.remove_metadata:
            elementTypes.append("metadata")
    if not elementTypes:
        return 0

    root = doc.documentElement
    assert root is not None
    elementsToRemove: list[Element] = []
    for elementType in elementTypes:
        elementsToRemove.extend(root.getElementsByTagName(elementType))

    for element in elementsToRemove:
        parent = element.parentNode
        assert parent is not None
        parent.removeChild(element)

    return len(elementsToRemove)


# =============================================================================
# Color Conversion
# =============================================================================
# (Implemented in svg_polish.colors; imported at the top of the module.)


# =============================================================================
# Main Optimization Pipeline
# =============================================================================


def scour_string(
    in_string: str | bytes, options: optparse.Values | None = None, stats: ScourStats | None = None
) -> str:
    """Optimize an SVG string and return the result.

    Parses *in_string* as XML, runs the full optimization pipeline
    (a fixed sequence of ~15 passes), and returns the optimized SVG string.
    The pipeline is order-dependent — later passes may depend on earlier ones
    (e.g. gradient dedup must happen before ID shortening).

    Pipeline passes (in order):

    1. **Sanitize options** — merge missing attributes from defaults, discard
       unknown attributes via :func:`sanitize_options`.
    2. **Bind precision contexts** — push thread-local
       :data:`~svg_polish.types._precision` contexts and a wider default
       :func:`decimal.getcontext` for the duration of the call via
       :func:`~svg_polish.types.precision_scope`. Restored on exit, even on
       exception, so concurrent ``scour_string`` calls are safe.
    3. **Remove descriptive elements** — strip ``<title>``, ``<desc>``,
       ``<metadata>`` per ``--keep-editor-data``.
    4. **Remove editor namespaces** — strip Inkscape/Illustrator/SVG-namespaced
       elements and attributes when ``keep_editor_data`` is False.
    5. **Namespace cleanup** — ensure the SVG namespace is declared, remove
       redundant ``xmlns:`` prefixes, remap namespace usage.
    6. **Strip comments** — remove XML comments when ``strip_comments`` is True.
    7. **Repair style** — fix broken CSS declarations, convert ``style``
       attributes to XML attributes where possible.
    8. **Convert colors** — replace named/rgb colors with shortest hex form
       when ``simple_colors`` is True.
    9. **Remove unreferenced elements** — delete elements inside/outside
       ``<defs>`` that nothing references.
    10. **Remove empty containers** — delete empty ``<defs>``, ``<g>``,
        ``<metadata>`` elements.
    11. **Gradient optimization** — remove duplicate gradient stops, collapse
        singly-referenced gradients, deduplicate identical gradients.
    12. **Group optimization** — merge sibling groups with common attributes,
        create new groups for runs of elements with identical attributes, move
        common attributes to parent, collapse nested groups.
    13. **Geometry optimization** — clean polygon/polyline points, optimize
        ``<path>`` ``d`` attributes (the full :func:`clean_path` pipeline),
        scour lengths/coordinates, remove default attribute values, optimize
        transforms, embed rasters as base64.
    14. **ID shortening** — rename IDs to shortest unique strings when
        ``shorten_ids`` is True.
    15. **Serialize** — write the DOM tree to a string with :func:`serialize_xml`,
        optionally prepending the XML prolog.

    **Thread-safety:** safe to invoke from multiple threads concurrently.
    Each thread gets its own :class:`~svg_polish.types.ScouringPrecision`
    state, and :func:`precision_scope` rolls back the contexts on exit.

    Args:
        in_string: Raw SVG/XML to optimize. Accepts ``str`` (assumed Unicode)
            or ``bytes`` (the encoding is detected from the XML declaration,
            so non-UTF-8 inputs like ISO-8859-15 are handled correctly).
        options: Optimizer options from :func:`parse_args`. ``None`` uses
            defaults via :func:`sanitize_options`.
        stats: Optional :class:`ScourStats` to collect metrics. A new
            instance is created internally if not provided.

    Returns:
        The optimized SVG string. Guaranteed to render identically to the
        input (lossless optimization). Includes a trailing newline.

    Example:
        >>> from svg_polish.optimizer import scour_string
        >>> result = scour_string(
        ...     '<svg xmlns="http://www.w3.org/2000/svg">'
        ...     '<rect fill="#ff0000"/></svg>'
        ... )
        >>> 'fill="red"' in result
        True
    """
    options = sanitize_options(options)
    if stats is None:
        stats = ScourStats()
    if options.cdigits < 0:
        options.cdigits = options.digits

    raw_engine = getattr(options, "decimal_engine", "decimal")
    engine: DecimalEngine = "float" if raw_engine == "float" else "decimal"
    with precision_scope(options.digits, options.cdigits, engine):
        return _scour_string_pipeline(in_string, options, stats)


def _scour_string_pipeline(in_string: str | bytes, options: optparse.Values, stats: ScourStats) -> str:
    """Run the optimization pipeline assuming :func:`precision_scope` is active.

    Internal helper extracted from :func:`scour_string` so that the public
    entry point can wrap the body in :func:`precision_scope` without forcing
    every line of the pipeline to be indented one level deeper.

    Pre-condition: the caller must already be inside ``precision_scope`` —
    ``_precision.ctx`` and ``_precision.ctx_c`` are read by the optimization
    passes and are not initialised here.
    """
    doc = _parse_xml(in_string, options)
    # parseString always produces a documentElement; bind to a local for clarity
    # and to give mypy a non-Optional handle for the rest of the pipeline.
    root = doc.documentElement
    assert root is not None, "parseString returned a document with no root element"

    # determine number of flowRoot elements in input document
    # flowRoot elements don't render at all on current browsers (04/2016)
    cnt_flowText_el = len(doc.getElementsByTagName("flowRoot"))
    if cnt_flowText_el:
        errmsg = "SVG input document uses {} flow text elements, which won't render on browsers!".format(
            cnt_flowText_el
        )
        if options.error_on_flowtext:
            raise Exception(errmsg)
        else:
            print("WARNING: {}".format(errmsg), file=sys.stderr)

    # remove descriptive elements
    stats.num_elements_removed += remove_descriptive_elements(doc, options)

    # remove unneeded namespaced elements/attributes added by common editors
    if options.keep_editor_data is False:
        stats.num_elements_removed += remove_namespaced_elements(root, unwanted_ns)
        stats.num_attributes_removed += remove_namespaced_attributes(root, unwanted_ns)

        # remove the xmlns: declarations now
        xmlnsDeclsToRemove: list[str] = []
        attrList = root.attributes
        for index in range(attrList.length):
            attr_node = attrList.item(index)
            assert attr_node is not None
            if attr_node.nodeValue in unwanted_ns:
                attr_name = attr_node.nodeName
                assert attr_name is not None
                xmlnsDeclsToRemove.append(attr_name)

        for attr in xmlnsDeclsToRemove:
            root.removeAttribute(attr)
        stats.num_attributes_removed += len(xmlnsDeclsToRemove)

    # ensure namespace for SVG is declared
    # TODO: what if the default namespace is something else (i.e. some valid namespace)?
    if root.getAttribute("xmlns") != "http://www.w3.org/2000/svg":
        root.setAttribute("xmlns", "http://www.w3.org/2000/svg")
        # TODO: throw error or warning?

    # check for redundant and unused SVG namespace declarations
    def xmlnsUnused(prefix: str, namespace: str) -> bool:
        """Return True if no element or attribute uses *prefix* in *namespace*."""
        if doc.getElementsByTagNameNS(namespace, "*"):
            return False
        else:
            for element in doc.getElementsByTagName("*"):
                for attribute in element.attributes.values():
                    if attribute.name.startswith(prefix):
                        return False
        return True

    attrList = root.attributes
    xmlnsDeclsToRemove = []
    redundantPrefixes: list[str] = []
    for i in range(attrList.length):
        attr_node = attrList.item(i)
        assert attr_node is not None
        name = attr_node.nodeName
        assert name is not None
        val = attr_node.nodeValue or ""
        if name.startswith("xmlns:"):
            if val == "http://www.w3.org/2000/svg":
                redundantPrefixes.append(name[6:])
                xmlnsDeclsToRemove.append(name)
            elif xmlnsUnused(name[6:], val):
                xmlnsDeclsToRemove.append(name)

    for attrName in xmlnsDeclsToRemove:
        root.removeAttribute(attrName)
    stats.num_attributes_removed += len(xmlnsDeclsToRemove)

    for prefix in redundantPrefixes:
        remap_namespace_prefix(root, prefix, "")

    # remap_namespace_prefix may have replaced the root element via parent.replaceChild,
    # so refresh the local handle before continuing.
    if redundantPrefixes:
        root = doc.documentElement
        assert root is not None

    if options.strip_comments:
        remove_comments(doc, stats)

    if options.strip_xml_space_attribute and root.hasAttribute("xml:space"):
        root.removeAttribute("xml:space")
        stats.num_attributes_removed += 1

    # repair style (remove unnecessary style properties and change them into XML attributes)
    stats.num_style_properties_fixed = repair_style(root, options)

    # convert colors to #RRGGBB format
    if options.simple_colors:
        stats.num_bytes_saved_in_colors = convert_colors(root)

    # remove unreferenced gradients/patterns outside of defs
    # and most unreferenced elements inside of defs
    while remove_unreferenced_elements(doc, options.keep_defs, stats) > 0:
        pass

    # remove empty defs, metadata, g
    # NOTE: these elements will be removed if they just have whitespace-only text nodes
    for tag in ["defs", "title", "desc", "metadata", "g"]:
        for elem in root.getElementsByTagName(tag):
            removeElem = not elem.hasChildNodes()
            if removeElem is False:
                for child in elem.childNodes:
                    if child.nodeType in [Node.ELEMENT_NODE, Node.CDATA_SECTION_NODE, Node.COMMENT_NODE]:
                        break
                    elif child.nodeType == Node.TEXT_NODE and not child.nodeValue.isspace():
                        break
                else:
                    removeElem = True
            if removeElem:
                parent = elem.parentNode
                assert parent is not None
                parent.removeChild(elem)
                stats.num_elements_removed += 1

    if options.strip_ids:
        referencedIDs = find_referenced_elements(root)
        identifiedElements = unprotected_ids(doc, options)
        stats.num_ids_removed += remove_unreferenced_ids(referencedIDs, identifiedElements)

    while remove_duplicate_gradient_stops(doc, stats) > 0:
        pass

    # remove gradients that are only referenced by one other gradient
    while collapse_singly_referenced_gradients(doc, stats) > 0:
        pass

    # remove duplicate gradients
    stats.num_elements_removed += remove_duplicate_gradients(doc)

    if options.group_collapse:
        stats.num_elements_removed += merge_sibling_groups_with_common_attributes(root)
    # create <g> elements if there are runs of elements with the same attributes.
    # this MUST be before move_common_attributes_to_parent_group.
    if options.group_create:
        create_groups_for_common_attributes(root, stats)

    # move common attributes to parent group
    # NOTE: the if the <svg> element's immediate children
    # all have the same value for an attribute, it must not
    # get moved to the <svg> element. The <svg> element
    # doesn't accept fill=, stroke= etc.!
    referencedIds = find_referenced_elements(root)
    for child in root.childNodes:
        # childNodes returns a broad union; move_common_attributes_to_parent_group
        # filters non-Element nodes via its early-return guard.
        stats.num_attributes_removed += move_common_attributes_to_parent_group(child, referencedIds)  # type: ignore[arg-type]

    # remove unused attributes from parent
    stats.num_attributes_removed += remove_unused_attributes_on_parent(root)

    # Collapse groups LAST, because we've created groups. If done before
    # moveAttributesToParentGroup, empty <g>'s may remain.
    if options.group_collapse:
        while remove_nested_groups(root, stats) > 0:
            pass

    # remove unnecessary closing point of polygons and scour points
    for polygon in root.getElementsByTagName("polygon"):
        stats.num_points_removed_from_polygon += clean_polygon(polygon, options)

    # scour points of polyline
    for polyline in root.getElementsByTagName("polyline"):
        clean_polyline(polyline, options)

    # clean path data
    for elem in root.getElementsByTagName("path"):
        if elem.getAttribute("d") == "":
            parent = elem.parentNode
            assert parent is not None
            parent.removeChild(elem)
        else:
            clean_path(elem, options, stats)

    # shorten ID names as much as possible
    if options.shorten_ids:
        stats.num_bytes_saved_in_ids += shorten_ids(doc, options.shorten_ids_prefix, options)

    # scour lengths (including coordinates) — single DOM traversal instead of 10
    _LENGTH_SCOUR_TYPES = frozenset(
        [
            "svg",
            "image",
            "rect",
            "circle",
            "ellipse",
            "line",
            "linearGradient",
            "radialGradient",
            "stop",
            "filter",
        ]
    )
    _LENGTH_SCOUR_ATTRS = (
        "x",
        "y",
        "width",
        "height",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "x1",
        "y1",
        "x2",
        "y2",
        "fx",
        "fy",
        "offset",
    )
    for elem in doc.getElementsByTagName("*"):
        if elem.tagName in _LENGTH_SCOUR_TYPES:
            for attr in _LENGTH_SCOUR_ATTRS:
                if elem.getAttribute(attr):
                    elem.setAttribute(attr, scour_length(elem.getAttribute(attr)))
    viewBox = root.getAttribute("viewBox")
    if viewBox:
        lengths = RE_COMMA_WSP.split(viewBox)
        lengths = [scour_unitless_length(length) for length in lengths]
        root.setAttribute("viewBox", " ".join(lengths))

    # more length scouring in this function
    stats.num_bytes_saved_in_lengths = reduce_precision(root)

    # remove default values of attributes
    stats.num_attributes_removed += remove_default_attribute_values(root, options)

    # reduce the length of transformation attributes
    stats.num_bytes_saved_in_transforms = optimize_transforms(root, options)

    # convert rasters references to base64-encoded strings
    if options.embed_rasters:
        for elem in root.getElementsByTagName("image"):
            stats.num_rasters_embedded += embed_rasters(elem, options)

    # properly size the SVG document (ideally width/height should be 100% with a viewBox)
    if options.enable_viewboxing:
        properly_size_doc(root, options)

    # output the document as a pretty string with a single space for indent
    # NOTE: removed pretty printing because of this problem:
    # http://ronrothman.com/public/leftbraned/xml-dom-minidom-toprettyxml-and-silly-whitespace/
    # rolled our own serialize function here to save on space, put id first, customize indentation, etc
    #  out_string = root.toprettyxml(' ')
    out_string = serialize_xml(root, options) + "\n"

    # return the string with its XML prolog and surrounding comments
    if options.strip_xml_prolog is False:
        total_output = '<?xml version="1.0" encoding="UTF-8"'
        if doc.standalone:
            total_output += ' standalone="yes"'
        total_output += "?>\n"
    else:
        total_output = ""

    for doc_child in doc.childNodes:
        if doc_child.nodeType == Node.ELEMENT_NODE:
            total_output += out_string
        else:  # doctypes, entities, comments
            total_output += doc_child.toxml() + "\n"

    return total_output


def scour_xml_file(filename: str, options: optparse.Values | None = None, stats: ScourStats | None = None) -> Document:
    """Optimize an SVG file and return the minidom Document (used primarily by tests)."""
    # sanitize options (take missing attributes from defaults, discard unknown attributes)
    options = sanitize_options(options)
    # we need to make sure infilename is set correctly (otherwise relative references in the SVG won't work)
    options.ensure_value("infilename", filename)

    # open the file and scour it
    # Read as bytes so that scour_string can let xml.dom.minidom.parseString
    # detect the encoding from the XML declaration (handles e.g. ISO-8859-15).
    with open(filename, "rb") as f:
        in_bytes = f.read()
    out_string = scour_string(in_bytes, options, stats=stats)

    # prepare the output xml.dom.minidom object
    # The output was just produced by scour_string from a defusedxml-validated
    # input, so it cannot contain forbidden entities. Use the std parser
    # directly to avoid re-running the security checks on trusted output.
    doc = xml.dom.minidom.parseString(out_string.encode("utf-8"))

    # since minidom does not seem to parse DTDs properly
    # manually declare all attributes with name "id" to be of type ID
    # (otherwise things like doc.getElementById() won't work)
    all_nodes = doc.getElementsByTagName("*")
    for node in all_nodes:
        try:
            node.setIdAttribute("id")
        except NotFoundErr:
            pass

    return doc


# =============================================================================
# Options Bridge (OptimizeOptions <-> optparse.Values)
# =============================================================================
#
# The CLI parser, ``parse_args``, and the file-I/O helpers (``maybe_gziped_file``,
# ``get_in_out``, ``generate_report``, ``start``, ``run``) live in
# :mod:`svg_polish.cli` so that importing :mod:`svg_polish.optimizer` does not
# pay the optparse-construction cost. The two helpers below are kept here
# because they are library-internal — used by :func:`scour_string` to accept
# the modern :class:`OptimizeOptions` as well as the legacy
# :class:`optparse.Values` namespace, without forcing a circular import on
# :mod:`svg_polish.cli`.


def generate_default_options() -> optparse.Values:
    """Return a fresh :class:`optparse.Values` populated with default settings.

    Internally backed by :class:`~svg_polish.options.OptimizeOptions` so the
    default values are guaranteed to match the public typed configuration
    (Sprint 3, M1).
    """
    return sanitize_options()


def sanitize_options(options: OptimizeOptions | optparse.Values | None = None) -> optparse.Values:
    """Return a complete options namespace with defaults filled in.

    Three input shapes are accepted, all return the same flat
    ``optparse.Values`` view that the legacy internal pipeline consumes:

    * ``None`` — every field comes from :class:`OptimizeOptions` defaults.
    * :class:`OptimizeOptions` — converted via the dataclass bridge.
    * :class:`optparse.Values` — user-provided values overlaid on defaults
      (matches the historical Scour behaviour).

    Defaults are sourced from :class:`~svg_polish.options.OptimizeOptions`
    rather than from the CLI parser so that this function works without
    having to import :mod:`svg_polish.cli` (avoids a circular import now that
    the parser lives in cli.py).
    """
    if isinstance(options, OptimizeOptions):
        return options._to_optparse_values()

    sanitized = OptimizeOptions()._to_optparse_values()
    if options is None:
        return sanitized

    # Overlay user-provided attributes on top of the dataclass defaults.
    # ``dir(options)`` includes optparse helpers (``ensure_value``, ``read_file``);
    # filter to plain data attributes by skipping callables and dunders.
    for key in dir(options):
        if key.startswith("_"):
            continue
        value = getattr(options, key)
        if callable(value):
            continue
        setattr(sanitized, key, value)
    return sanitized
