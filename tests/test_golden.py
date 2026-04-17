"""Golden output regression tests.

These tests lock down the exact output of the optimizer to catch any
behavioral changes during refactoring. If a test fails, the refactoring
has altered optimization behavior — investigate before updating the golden file.
"""

from __future__ import annotations

from pathlib import Path

from svg_polish.cli import parse_args
from svg_polish.optimizer import scour_string

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestGoldenOutput:
    """Exact char-for-char output comparison against golden files."""

    def test_complex_scene_default(self):
        result = scour_string(_read("complex-scene.svg"))
        expected = _read("golden-complex-scene.svg")
        assert result == expected

    def test_xlink_references_default(self):
        result = scour_string(_read("xlink-references.svg"))
        expected = _read("golden-xlink-references.svg")
        assert result == expected

    def test_rename_ids_shortened(self):
        options = parse_args(["--shorten-ids"])
        result = scour_string(_read("rename-ids-in-style.svg"), options)
        expected = _read("golden-rename-ids-shortened.svg")
        assert result == expected

    def test_complex_scene_max_optimization(self):
        options = parse_args(
            [
                "--enable-viewboxing",
                "--enable-comment-stripping",
                "--shorten-ids",
                "--create-groups",
                "--disable-style-to-xml",
            ]
        )
        result = scour_string(_read("complex-scene.svg"), options)
        expected = _read("golden-complex-maxopt.svg")
        assert result == expected

    def test_style_css_inline_default(self):
        """Inline <style> CSS with CDATA blocks must round-trip identically."""
        result = scour_string(_read("css-reference.svg"))
        expected = _read("golden-style-css-reference.svg")
        assert result == expected

    def test_inline_script_preserved(self):
        """Inline <script> elements (with CDATA) must be preserved verbatim."""
        result = scour_string(_read("inline-script.svg"))
        expected = _read("golden-inline-script.svg")
        assert result == expected

    def test_custom_namespace_keep_editor_data(self):
        """With --keep-editor-data, custom editor namespaces (Inkscape, foo) are kept."""
        options = parse_args(["--keep-editor-data"])
        result = scour_string(_read("inkscape.svg"), options)
        expected = _read("golden-inkscape-keep-editor.svg")
        assert result == expected
