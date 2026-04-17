"""Tests for the svg_polish public API."""

from __future__ import annotations

from pathlib import Path

import pytest

from svg_polish import __version__, optimize, optimize_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestVersion:
    """Tests for version information."""

    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_version_is_1_0_0(self):
        assert __version__ == "1.0.0"


class TestOptimize:
    """Tests for the optimize() function."""

    MINIMAL_SVG = '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>\n'

    def test_minimal_svg(self):
        result = optimize(self.MINIMAL_SVG)
        assert "svg" in result
        assert "xmlns" in result

    def test_bytes_input(self):
        result = optimize(self.MINIMAL_SVG.encode("utf-8"))
        assert isinstance(result, str)
        assert "svg" in result

    def test_removes_editor_data(self):
        svg_with_inkscape = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<svg xmlns="http://www.w3.org/2000/svg"'
            ' xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">'
            "<inkscape:foo/>"
            "</svg>"
        )
        result = optimize(svg_with_inkscape)
        assert "inkscape" not in result

    def test_reduces_size(self):
        svg_with_redundancy = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<svg xmlns="http://www.w3.org/2000/svg"'
            ' xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">'
            "<sodipodi:namedview/>"
            '<rect x="0" y="0" width="100" height="100"'
            ' style="fill:#ff0000;stroke:#000000"/>'
            "</svg>"
        )
        result = optimize(svg_with_redundancy)
        assert len(result) <= len(svg_with_redundancy)

    def test_none_options(self):
        result = optimize(self.MINIMAL_SVG, options=None)
        assert "svg" in result

    def test_preserves_content(self):
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100" height="100"/>'
            "</svg>"
        )
        result = optimize(svg)
        assert "rect" in result
        assert "width" in result


class TestOptimizeFile:
    """Tests for the optimize_file() function."""

    def test_optimize_file(self):
        filepath = str(FIXTURES_DIR / "minimal.svg")
        result = optimize_file(filepath)
        assert "svg" in result
        assert isinstance(result, str)

    def test_optimize_svg_file(self):
        filepath = str(FIXTURES_DIR / "ids.svg")
        result = optimize_file(filepath)
        assert "svg" in result

    def test_nonexistent_file_raises(self):
        with pytest.raises(Exception):
            optimize_file("/nonexistent/file.svg")


class TestImports:
    """Test that all public symbols are importable."""

    def test_import_optimize(self):
        from svg_polish import optimize

        assert callable(optimize)

    def test_import_optimize_file(self):
        from svg_polish import optimize_file

        assert callable(optimize_file)

    def test_import_version(self):
        from svg_polish import __version__

        assert __version__

    def test_import_optimizer_module(self):
        from svg_polish.optimizer import parse_args, scour_string, scour_xml_file

        assert callable(scour_string)
        assert callable(scour_xml_file)
        assert callable(parse_args)

    def test_import_stats(self):
        from svg_polish.stats import ScourStats

        stats = ScourStats()
        assert stats.num_elements_removed == 0

    def test_import_svg_regex(self):
        from svg_polish.svg_regex import svg_parser

        result = svg_parser.parse("M 10,20 30,40")
        assert len(result) == 1
        assert result[0][0] == "M"

    def test_import_svg_transform(self):
        from svg_polish.svg_transform import svg_transform_parser

        result = svg_transform_parser.parse("translate(50, 50)")
        assert len(result) == 1
        assert result[0][0] == "translate"

    def test_import_css(self):
        from svg_polish.css import parseCssString

        result = parseCssString("foo { bar: baz }")
        assert len(result) == 1
