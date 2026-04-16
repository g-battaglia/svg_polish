"""Tests for CLI flag behavior.

Verifies that command-line flags passed via parse_args() produce the
expected changes in the optimized SVG output.
"""

from __future__ import annotations

from svg_polish.optimizer import parse_args, scourString

# ---------------------------------------------------------------------------
# --strip-xml-prolog
# ---------------------------------------------------------------------------


class TestStripXmlProlog:
    """--strip-xml-prolog removes the <?xml ...?> declaration."""

    def test_strip_xml_prolog(self) -> None:
        """With --strip-xml-prolog, the XML prolog is removed."""
        svg = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        options = parse_args(["--strip-xml-prolog"])
        result = scourString(svg, options)
        assert "<?xml" not in result

    def test_default_keeps_xml_prolog(self) -> None:
        """Without --strip-xml-prolog, the XML prolog is preserved."""
        svg = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        options = parse_args([])
        result = scourString(svg, options)
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
        result = scourString(svg, options)
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
        result = scourString(svg, options)
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
        result = scourString(svg, options)
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
        result = scourString(svg, options)
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
        result = scourString(svg, options)
        assert "viewBox" in result
        # The viewBox should reflect the width/height
        assert "0 0 100 200" in result
