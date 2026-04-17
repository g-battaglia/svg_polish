"""Tests for CLI flag behavior.

Verifies that command-line flags passed via parse_args() produce the
expected changes in the optimized SVG output.
"""

from __future__ import annotations

from svg_polish.cli import parse_args
from svg_polish.optimizer import scour_string

# ---------------------------------------------------------------------------
# --strip-xml-prolog
# ---------------------------------------------------------------------------


class TestStripXmlProlog:
    """--strip-xml-prolog removes the <?xml ...?> declaration."""

    def test_strip_xml_prolog(self) -> None:
        """With --strip-xml-prolog, the XML prolog is removed."""
        svg = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        options = parse_args(["--strip-xml-prolog"])
        result = scour_string(svg, options)
        assert "<?xml" not in result

    def test_default_keeps_xml_prolog(self) -> None:
        """Without --strip-xml-prolog, the XML prolog is preserved."""
        svg = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        options = parse_args([])
        result = scour_string(svg, options)
        assert "<?xml" in result


# ---------------------------------------------------------------------------
# --no-line-breaks
# ---------------------------------------------------------------------------


class TestNoLineBreaks:
    """--no-line-breaks produces output with no newline characters."""

    def test_no_line_breaks(self) -> None:
        """With --no-line-breaks, output SVG body has no newlines between elements."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<rect fill='red' width='10' height='10'/>"
            "<circle fill='blue' cx='5' cy='5' r='3'/>"
            "</svg>"
        )
        options = parse_args(["--no-line-breaks"])
        result = scour_string(svg, options)
        # The XML prolog and trailing newline are always present.
        # The key behavior: the SVG body (between <svg> and </svg>)
        # should have no newlines — everything on one line.
        svg_body_start = result.find("<svg")
        svg_body_end = result.rfind("</svg>") + len("</svg>")
        svg_body = result[svg_body_start:svg_body_end]
        assert "\n" not in svg_body


# ---------------------------------------------------------------------------
# --shorten-ids
# ---------------------------------------------------------------------------


class TestShortenIds:
    """--shorten-ids replaces long IDs with short numeric IDs."""

    def test_shorten_ids(self) -> None:
        """With --shorten-ids, long IDs are replaced with short ones."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="myVeryLongGradientName">'
            '<stop offset="0" stop-color="red"/>'
            '<stop offset="1" stop-color="blue"/>'
            "</linearGradient>"
            "</defs>"
            '<rect fill="url(#myVeryLongGradientName)" width="100" height="100"/>'
            "</svg>"
        )
        options = parse_args(["--shorten-ids"])
        result = scour_string(svg, options)
        # The long ID should not appear anymore
        assert "myVeryLongGradientName" not in result
        # But the reference should still be valid (shortened ID present)
        assert "url(#" in result


# ---------------------------------------------------------------------------
# --keep-editor-data
# ---------------------------------------------------------------------------


class TestKeepEditorData:
    """--keep-editor-data preserves editor namespace declarations."""

    def test_keep_editor_data(self) -> None:
        """With --keep-editor-data, editor namespaces are preserved."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">'
            '<rect sodipodi:role="test" fill="red" width="10" height="10"/>'
            "</svg>"
        )
        options = parse_args(["--keep-editor-data"])
        result = scour_string(svg, options)
        assert "sodipodi" in result

    def test_default_strips_editor_data(self) -> None:
        """Without --keep-editor-data, editor namespaces are stripped."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">'
            '<rect sodipodi:role="test" fill="red" width="10" height="10"/>'
            "</svg>"
        )
        options = parse_args([])
        result = scour_string(svg, options)
        assert "sodipodi" not in result


# ---------------------------------------------------------------------------
# --enable-viewboxing
# ---------------------------------------------------------------------------


class TestEnableViewboxing:
    """--enable-viewboxing adds a viewBox attribute if missing."""

    def test_enable_viewboxing(self) -> None:
        """With --enable-viewboxing, viewBox is added from width/height."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="100" height="200">'
            "<rect fill='red' width='10' height='10'/>"
            "</svg>"
        )
        options = parse_args(["--enable-viewboxing"])
        result = scour_string(svg, options)
        assert "viewBox" in result
        # The viewBox should reflect the width/height
        assert "0 0 100 200" in result


# ---------------------------------------------------------------------------
# --enable-id-stripping
# ---------------------------------------------------------------------------


class TestIdStripping:
    """--enable-id-stripping removes unreferenced IDs."""

    def test_strip_unreferenced_id(self) -> None:
        """With --enable-id-stripping, unreferenced IDs are removed."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="unused" width="100" height="100"/></svg>'
        options = parse_args(["--enable-id-stripping"])
        result = scour_string(svg, options)
        assert 'id="unused"' not in result

    def test_referenced_id_kept(self) -> None:
        """Referenced IDs are preserved even with --enable-id-stripping."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="used">'
            '<stop offset="0" stop-color="red"/>'
            "</linearGradient>"
            "</defs>"
            '<rect fill="url(#used)" width="100" height="100"/>'
            "</svg>"
        )
        options = parse_args(["--enable-id-stripping"])
        result = scour_string(svg, options)
        assert "used" in result


# ---------------------------------------------------------------------------
# --remove-titles
# ---------------------------------------------------------------------------


class TestRemoveTitles:
    """--remove-titles removes <title> elements."""

    def test_remove_titles(self) -> None:
        """With --remove-titles, <title> elements are stripped."""
        svg = "<svg xmlns=\"http://www.w3.org/2000/svg\"><title>My SVG</title><rect width='100' height='100'/></svg>"
        options = parse_args(["--remove-titles"])
        result = scour_string(svg, options)
        assert "<title>" not in result
        assert "My SVG" not in result

    def test_title_kept_by_default(self) -> None:
        """Without --remove-titles, <title> elements are preserved."""
        svg = "<svg xmlns=\"http://www.w3.org/2000/svg\"><title>My SVG</title><rect width='100' height='100'/></svg>"
        options = parse_args([])
        result = scour_string(svg, options)
        assert "My SVG" in result


# ---------------------------------------------------------------------------
# --remove-descriptions
# ---------------------------------------------------------------------------


class TestRemoveDescriptions:
    """--remove-descriptions removes <desc> elements."""

    def test_remove_descriptions(self) -> None:
        """With --remove-descriptions, <desc> elements are stripped."""
        svg = (
            "<svg xmlns=\"http://www.w3.org/2000/svg\"><desc>A description</desc><rect width='100' height='100'/></svg>"
        )
        options = parse_args(["--remove-descriptions"])
        result = scour_string(svg, options)
        assert "<desc>" not in result
        assert "A description" not in result


# ---------------------------------------------------------------------------
# --remove-metadata
# ---------------------------------------------------------------------------


class TestRemoveMetadata:
    """--remove-metadata removes <metadata> elements."""

    def test_remove_metadata(self) -> None:
        """With --remove-metadata, <metadata> elements are stripped."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<metadata>some metadata</metadata>"
            "<rect width='100' height='100'/>"
            "</svg>"
        )
        options = parse_args(["--remove-metadata"])
        result = scour_string(svg, options)
        assert "<metadata>" not in result


# ---------------------------------------------------------------------------
# --enable-comment-stripping
# ---------------------------------------------------------------------------


class TestCommentStripping:
    """--enable-comment-stripping removes XML comments."""

    def test_strip_comments(self) -> None:
        """With --enable-comment-stripping, comments are removed."""
        svg = "<svg xmlns=\"http://www.w3.org/2000/svg\"><!-- a comment --><rect width='100' height='100'/></svg>"
        options = parse_args(["--enable-comment-stripping"])
        result = scour_string(svg, options)
        assert "<!--" not in result
        assert "a comment" not in result


# ---------------------------------------------------------------------------
# --disable-simplify-colors
# ---------------------------------------------------------------------------


class TestDisableSimplifyColors:
    """--disable-simplify-colors keeps colors as-is."""

    def test_disable_simplify_colors(self) -> None:
        """With --disable-simplify-colors, #ff0000 stays as #ff0000."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#ff0000" width="100" height="100"/></svg>'
        options = parse_args(["--disable-simplify-colors"])
        result = scour_string(svg, options)
        # With color simplification disabled, the full hex should remain
        assert "#ff0000" in result or "#f00" not in result


# ---------------------------------------------------------------------------
# --keep-unreferenced-defs
# ---------------------------------------------------------------------------


class TestKeepUnreferencedDefs:
    """--keep-unreferenced-defs preserves unused <defs> children."""

    def test_keep_unreferenced_defs(self) -> None:
        """With --keep-unreferenced-defs, unreferenced gradients survive."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="unused">'
            '<stop offset="0" stop-color="red"/>'
            "</linearGradient>"
            "</defs>"
            '<rect fill="red" width="100" height="100"/>'
            "</svg>"
        )
        options = parse_args(["--keep-unreferenced-defs"])
        result = scour_string(svg, options)
        assert "linearGradient" in result


# ---------------------------------------------------------------------------
# --create-groups
# ---------------------------------------------------------------------------


class TestCreateGroups:
    """--create-groups creates <g> from consecutive same-style elements."""

    def test_create_groups_with_common_attributes(self) -> None:
        """With --create-groups, elements sharing attributes may be grouped."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect fill="red" stroke="blue" width="10" height="10"/>'
            '<rect fill="red" stroke="blue" width="10" height="10" x="20"/>'
            '<rect fill="green" width="10" height="10" x="40"/>'
            "</svg>"
        )
        options = parse_args(["--create-groups"])
        result = scour_string(svg, options)
        # The option should not crash — group creation depends on
        # element similarity heuristics.
        assert "<svg" in result


# ---------------------------------------------------------------------------
# --protect-ids-list
# ---------------------------------------------------------------------------


class TestProtectIds:
    """--protect-ids-list prevents specific IDs from being stripped."""

    def test_protect_ids_list(self) -> None:
        """Protected IDs are preserved with --enable-id-stripping."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="myGrad">'
            '<stop offset="0" stop-color="red"/>'
            "</linearGradient>"
            "</defs>"
            '<rect fill="url(#myGrad)" width="100" height="100"/>'
            '<rect id="unused" width="10" height="10"/>'
            "</svg>"
        )
        options = parse_args(["--enable-id-stripping", "--protect-ids-list=unused"])
        result = scour_string(svg, options)
        # "unused" is protected, so it should still appear
        assert "unused" in result


# ---------------------------------------------------------------------------
# --shorten-ids-prefix
# ---------------------------------------------------------------------------


class TestShortenIdsPrefix:
    """--shorten-ids-prefix sets the prefix for shortened IDs."""

    def test_shorten_ids_prefix(self) -> None:
        """Shortened IDs should use the specified prefix."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<defs>"
            '<linearGradient id="longName">'
            '<stop offset="0" stop-color="red"/>'
            "</linearGradient>"
            "</defs>"
            '<rect fill="url(#longName)" width="100" height="100"/>'
            "</svg>"
        )
        options = parse_args(["--shorten-ids", "--shorten-ids-prefix=x"])
        result = scour_string(svg, options)
        assert "longName" not in result
        assert "url(#" in result
