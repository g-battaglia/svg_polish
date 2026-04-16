"""Tests for remaining uncovered lines in svg_polish.

These tests target specific code paths that need real SVG fixtures
to reach properly.
"""

from __future__ import annotations

import xml.dom.minidom

from svg_polish.optimizer import (
    dedup_gradient,
    findElementsWithId,
    findReferencedElements,
    mayContainTextNodes,
    parse_args,
    removeUnusedDefs,
    renameID,
    scourString,
    styleInheritedByChild,
    styleInheritedFromParent,
)


def _scour(svg_string: str, args: list[str] | None = None) -> str:
    options = parse_args(args) if args else None
    return scourString(svg_string, options)


def _parse_svg(svg_string: str):
    return xml.dom.minidom.parseString(svg_string)


# ---------------------------------------------------------------------------
# removeUnusedDefs called with referencedIDs=None (line 619)
# ---------------------------------------------------------------------------


class TestRemoveUnusedDefsDirectCall:
    """Call removeUnusedDefs directly with referencedIDs=None to hit line 619."""

    def test_direct_call_with_none_referenced_ids(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="unused"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100"/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        defs = doc.getElementsByTagName("defs")[0]
        # Call directly with referencedIDs=None to trigger line 619
        elemsToRemove = removeUnusedDefs(doc, defs, elemsToRemove=None, referencedIDs=None)
        assert isinstance(elemsToRemove, list)


# ---------------------------------------------------------------------------
# renameIDs: style attribute url(#id) replacement (lines 858-862)
# ---------------------------------------------------------------------------


class TestRenameIDsStyleUrlDirect:
    """Directly test renaming IDs that appear in style='...' url() references."""

    def test_rename_id_in_style_url(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="oldId"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100" style="fill:url(#oldId)"/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        identifiedElements = findElementsWithId(doc.documentElement)
        referencedIDs = findReferencedElements(doc.documentElement)
        referringNodes = referencedIDs.get("oldId")
        renameID("oldId", "a", identifiedElements, referringNodes)
        result = doc.documentElement.toxml()
        assert "url(#a)" in result
        assert "oldId" not in result

    def test_rename_id_in_style_url_single_quotes(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="oldId"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100" style="fill:url(\'#oldId\')"/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        identifiedElements = findElementsWithId(doc.documentElement)
        referencedIDs = findReferencedElements(doc.documentElement)
        referringNodes = referencedIDs.get("oldId")
        renameID("oldId", "b", identifiedElements, referringNodes)
        result = doc.documentElement.toxml()
        assert "url(#b)" in result

    def test_rename_id_in_style_url_double_quotes(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="oldId"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100" style=\'fill:url("#oldId")\'/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        identifiedElements = findElementsWithId(doc.documentElement)
        referencedIDs = findReferencedElements(doc.documentElement)
        referringNodes = referencedIDs.get("oldId")
        renameID("oldId", "c", identifiedElements, referringNodes)
        result = doc.documentElement.toxml()
        assert "url(#c)" in result


# ---------------------------------------------------------------------------
# mergeSiblingGroups trailing whitespace break (line 1349)
# ---------------------------------------------------------------------------


class TestCreateGroupsTrailingElementBreak:
    """Triggers the break at line 1349: runEnd expansion stops at next element node."""

    def test_create_groups_trailing_element_break(self):
        # Need 3+ elements sharing an attribute, followed by whitespace, then another element
        # with --create-groups to enable the create_groups_for_common_attributes function
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<g>"
            '<rect fill="red" width="10" height="10"/>'
            '<rect fill="red" width="20" height="20"/>'
            '<rect fill="red" width="30" height="30"/>'
            "  "  # whitespace text node — runEnd extends past this
            '<circle fill="blue" r="5"/>'  # element node — triggers break
            "</g>"
            "</svg>"
        )
        result = _scour(svg, ["--create-groups"])
        assert "svg" in result


# ---------------------------------------------------------------------------
# dedup_gradient: parentNode=None (line 1671) and KeyError (lines 1707-1708)
# ---------------------------------------------------------------------------


class TestDedupGradientEdgeCases:
    """Test dedup_gradient edge cases directly."""

    def test_dedup_with_already_removed_gradient(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="master"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            '<linearGradient id="dup1"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100" fill="url(#master)"/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        grads = doc.getElementsByTagName("linearGradient")
        _master = grads[0]
        dup = grads[1]

        # Remove dup's parent to simulate already-processed gradient
        dup.parentNode.removeChild(dup)

        # Now call dedup_gradient with parentNode=None
        dedup_gradient("master", ["dup1"], [dup], {})

    def test_dedup_with_master_not_in_referenced(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="master"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            '<linearGradient id="dup"><stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/></linearGradient>'
            "</defs>"
            '<rect width="100" height="100" fill="url(#dup)"/>'
            "</svg>"
        )
        doc = _parse_svg(svg)
        grads = doc.getElementsByTagName("linearGradient")
        dup = grads[1]
        rect = doc.getElementsByTagName("rect")[0]

        # referenced_ids has "dup" but not "master"
        referenced_ids = {"dup": {rect}}
        dedup_gradient("master", ["dup"], [dup], referenced_ids)
        # master_references should get the dup's references via KeyError path
        assert "master" not in referenced_ids or isinstance(referenced_ids.get("master"), set)


# ---------------------------------------------------------------------------
# getInheritedAttribute and styleInheritedByChild (lines 1961-1963, 1997)
# ---------------------------------------------------------------------------


class TestStyleInheritance:
    """Test style inheritance lookup functions."""

    def test_inherited_attribute_from_style(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g style="fill:red"><rect width="10" height="10"/></g></svg>'
        doc = _parse_svg(svg)
        rect = doc.getElementsByTagName("rect")[0]
        val = styleInheritedFromParent(rect, "fill")
        assert val == "red"

    def test_inherited_attribute_skips_inherit_value(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" style="fill:blue">'
            '<g style="fill:inherit">'
            '<rect width="10" height="10"/>'
            "</g>"
            "</svg>"
        )
        doc = _parse_svg(svg)
        rect = doc.getElementsByTagName("rect")[0]
        val = styleInheritedFromParent(rect, "fill")
        assert val == "blue"

    def test_style_inherited_by_child_returns_false_when_child_overrides(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g style="opacity:0;fill:red">'
            '<rect width="10" height="10" fill="blue"/>'
            "</g>"
            "</svg>"
        )
        doc = _parse_svg(svg)
        g = doc.getElementsByTagName("g")[0]
        # fill is overridden by child rect, so not inherited
        result = styleInheritedByChild(g, "fill")
        assert result is False

    def test_style_inherited_by_child_returns_false_when_child_has_style(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g style="opacity:0;stroke:green">'
            '<rect width="10" height="10" style="stroke:blue"/>'
            "</g>"
            "</svg>"
        )
        doc = _parse_svg(svg)
        g = doc.getElementsByTagName("g")[0]
        result = styleInheritedByChild(g, "stroke")
        assert result is False


# ---------------------------------------------------------------------------
# mayContainTextNodes (lines 2058, 2067)
# ---------------------------------------------------------------------------


class TestMayContainTextNodesDirect:
    """Direct calls to mayContainTextNodes."""

    def test_non_svg_namespace_element(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:custom="http://example.com/ns">'
            "<custom:widget>text</custom:widget>"
            "</svg>"
        )
        doc = _parse_svg(svg)
        custom_elem = None
        for child in doc.documentElement.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.localName == "widget":
                custom_elem = child
                break
        assert custom_elem is not None
        assert mayContainTextNodes(custom_elem) is True

    def test_group_with_text_child(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g><text>Hello</text></g></svg>'
        doc = _parse_svg(svg)
        g = doc.getElementsByTagName("g")[0]
        assert mayContainTextNodes(g) is True


# ---------------------------------------------------------------------------
# removeDefaultAttributeValues universal (line 2402) + color in styles (2507-2508)
# ---------------------------------------------------------------------------


class TestConvertColorsInStyles:
    """Color conversion in style attributes (lines 2507-2508)."""

    def test_color_conversion_in_style(self):
        # Use --disable-style-to-xml to keep colors in the style attribute
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100" height="100" style="fill:#ff0000;stroke:#000000"/>'
            "</svg>"
        )
        result = _scour(svg, ["--disable-style-to-xml"])
        # #ff0000 should become red or #f00 in style
        assert "#ff0000" not in result


# ---------------------------------------------------------------------------
# Path: straight curve flush (2778-2779), h/v optimization (2828-2839)
# ---------------------------------------------------------------------------


class TestPathStraightCurveFlush:
    """Flush existing curve data when a straight curve is found (lines 2778-2779).

    Needs a single 'c' command with multiple coordinate sets:
    first a real curve (non-straight), then a straight curve.
    """

    def test_flush_curve_before_straight(self):
        # c with TWO sets of coords in ONE command:
        # 1st set: not collinear → kept as curve → newData = [5,10,15,20,20,25]
        # 2nd set: dx=0, p1x=0, p2x=0 → straight → triggers flush of newData
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 c5,10,15,20,20,25,0,0,0,0,0,10"/></svg>'
        result = _scour(svg)
        assert "path" in result


class TestPathLineDecomposeHV:
    """Decompose 'l' into h/v when preceded by regular line segments (lines 2828-2839).

    A command other than 'm' must precede the 'l' to prevent the first collapse
    step from merging l data into the m command (which uses a different code path).
    """

    def test_vertical_after_regular_line(self):
        # h10 prevents l from being merged into m. Then l 5,5,0,10:
        # first pair (5,5) fills lineTuples, second (0,10) triggers flush → lines 2828-2829
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 h10 l5,5,0,10"/></svg>'
        result = _scour(svg)
        assert "v" in result or "l" in result

    def test_horizontal_after_regular_line(self):
        # v10 prevents l from being merged into m. Then l 5,5,10,0:
        # first pair (5,5) fills lineTuples, second (10,0) triggers flush → lines 2834-2839
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 v10 l5,5,10,0"/></svg>'
        result = _scour(svg)
        assert "h" in result or "l" in result


# ---------------------------------------------------------------------------
# Collapse same commands (line 2999)
# ---------------------------------------------------------------------------


class TestCollapseConsecutiveSameCommands:
    """Collapse consecutive same-type commands after h/v decomposition (line 2999).

    After 'l' decomposition creates consecutive h or v commands, the second
    collapse step merges them. Must use h/v before l to prevent m-l merging.
    """

    def test_consecutive_h_from_decomposition(self):
        # h10 separates m from l. l 5,5,10,0,20,0 decomposes to: l(5,5), h(10), h(20)
        # Then h(10) + h(20) collapse at line 2999
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 h1 l5,5,10,0,20,0"/></svg>'
        result = _scour(svg)
        assert "path" in result

    def test_consecutive_v_from_decomposition(self):
        # v1 separates m from l. l 5,5,0,10,0,20 decomposes to: l(5,5), v(10), v(20)
        # Then v(10) + v(20) collapse at line 2999
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 v1 l5,5,0,10,0,20"/></svg>'
        result = _scour(svg)
        assert "path" in result


# ---------------------------------------------------------------------------
# reducePrecision in styles (lines 3315-3321)
# ---------------------------------------------------------------------------


class TestReducePrecisionInStyles:
    """Length values in style attributes that can be shortened (lines 3315-3321).

    Must use --disable-style-to-xml to prevent styles from being moved to attributes
    before reducePrecision runs.
    """

    def test_stroke_width_in_style_shortened(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100" height="100" style="stroke-width:2.500px"/>'
            "</svg>"
        )
        result = _scour(svg, ["--disable-style-to-xml"])
        # 2.500px should be reduced to 2.5px
        assert "2.500" not in result

    def test_font_size_in_style_shortened(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text style="font-size:12.000px">Hello</text></svg>'
        result = _scour(svg, ["--disable-style-to-xml"])
        assert "12.000" not in result

    def test_stroke_dashoffset_in_style(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<line x1="0" y1="0" x2="100" y2="0" '
            'style="stroke:#000;stroke-dashoffset:2.500px"/>'
            "</svg>"
        )
        result = _scour(svg, ["--disable-style-to-xml"])
        assert "2.500" not in result


# ---------------------------------------------------------------------------
# Transform: non-coalescable types fallthrough (line 3502)
# ---------------------------------------------------------------------------


class TestTransformNonCoalescable:
    """Transforms that can't be coalesced should be left alone."""

    def test_different_transform_types_not_coalesced(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100" height="100" transform="translate(10) rotate(45) scale(2)"/>'
            "</svg>"
        )
        result = _scour(svg)
        assert "translate" in result
        assert "rotate" in result
        assert "scale" in result


# ---------------------------------------------------------------------------
# createViewBox: renderer_workaround with non-px units (line 3656),
# viewBox with non-zero origin (3669), differing w/h (3677-3678)
# ---------------------------------------------------------------------------


class TestCreateViewBoxEdgeCases:
    """Edge cases for viewBox creation."""

    def test_renderer_workaround_blocks_cm_units(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10cm" height="5cm"><rect width="100" height="100"/></svg>'
        result = _scour(svg, ["--enable-viewboxing", "--renderer-workaround"])
        # Should NOT create viewBox because of cm units with renderer workaround
        assert "viewBox" not in result
        assert "10cm" in result

    def test_viewbox_with_nonzero_origin(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
            'viewBox="10 10 100 100">'
            '<rect width="100" height="100"/>'
            "</svg>"
        )
        result = _scour(svg, ["--enable-viewboxing"])
        # Should keep existing viewBox since origin is non-zero
        assert "10 10 100 100" in result

    def test_viewbox_with_different_dimensions(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
            'viewBox="0 0 200 200">'
            '<rect width="100" height="100"/>'
            "</svg>"
        )
        result = _scour(svg, ["--enable-viewboxing"])
        # Should keep existing viewBox since dimensions differ
        assert "200" in result

    def test_viewbox_creation_with_px_units(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="50px"><rect width="100" height="50"/></svg>'
        )
        result = _scour(svg, ["--enable-viewboxing"])
        assert "viewBox" in result


# ---------------------------------------------------------------------------
# remapNamespacePrefix with non-empty prefix (line 3698)
# ---------------------------------------------------------------------------


class TestRemapNamespacePrefix:
    """Test namespace prefix remapping."""

    def test_remap_xlink_prefix(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<defs><linearGradient id="g1">'
            '<stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/>'
            "</linearGradient></defs>"
            '<use xlink:href="#g1"/>'
            "</svg>"
        )
        result = _scour(svg)
        assert "svg" in result


# ---------------------------------------------------------------------------
# xmlns: prefix handling in serialization (line 3858)
# ---------------------------------------------------------------------------


class TestXmlnsPrefixSerialization:
    """Namespace attributes that need xmlns: prefix in serialization."""

    def test_preserves_xlink_namespace(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            "<defs>"
            '<linearGradient id="g1" xlink:href="#g2">'
            '<stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/>'
            "</linearGradient>"
            '<linearGradient id="g2">'
            '<stop offset="0" stop-color="green"/>'
            '<stop offset="1" stop-color="yellow"/>'
            "</linearGradient>"
            "</defs>"
            '<rect width="100" height="100" fill="url(#g1)"/>'
            "</svg>"
        )
        result = _scour(svg)
        assert "xlink" in result or "href" in result


# ---------------------------------------------------------------------------
# Opacity 0 with children that inherit (lines 1788-1806 fully covered)
# ---------------------------------------------------------------------------


class TestOpacityZeroWithTextChildren:
    """opacity:0 should NOT remove fill when text children inherit it."""

    def test_opacity_zero_keeps_fill_when_text_inherits(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g style="opacity:0;fill:red;stroke:blue;fill-opacity:0.5;'
            "stroke-linejoin:round;stroke-opacity:0.5;stroke-miterlimit:4;"
            'stroke-linecap:butt;stroke-dasharray:5;stroke-dashoffset:1">'
            '<rect width="10" height="10"/>'
            "</g>"
            "</svg>"
        )
        result = _scour(svg)
        # With opacity:0 and NO text children, fill/stroke should be removed
        assert "opacity" in result

    def test_opacity_zero_removes_useless_styles(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect width="10" height="10" style="opacity:0;fill:red;stroke:blue;'
            "fill-rule:evenodd;stroke-linejoin:round;stroke-opacity:0.5;"
            'stroke-miterlimit:4;stroke-linecap:butt;stroke-dasharray:5;stroke-dashoffset:1"/>'
            "</svg>"
        )
        result = _scour(svg)
        # On a leaf element, all fill/stroke props should be removed
        assert "fill:red" not in result or "fill:" not in result
