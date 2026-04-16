"""Golden output regression tests.

These tests lock down the exact output of the optimizer to catch any
behavioral changes during refactoring. If a test fails, the refactoring
has altered optimization behavior — investigate before updating the golden file.
"""

from __future__ import annotations

from pathlib import Path

from svg_polish.optimizer import parse_args, scourString

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestGoldenOutput:
    """Exact char-for-char output comparison against golden files."""

    def test_complex_scene_default(self):
        result = scourString(_read("complex-scene.svg"))
        expected = _read("golden-complex-scene.svg")
        assert result == expected

    def test_xlink_references_default(self):
        result = scourString(_read("xlink-references.svg"))
        expected = _read("golden-xlink-references.svg")
        assert result == expected

    def test_rename_ids_shortened(self):
        options = parse_args(["--shorten-ids"])
        result = scourString(_read("rename-ids-in-style.svg"), options)
        expected = _read("golden-rename-ids-shortened.svg")
        assert result == expected

    def test_complex_scene_max_optimization(self):
        options = parse_args([
            "--enable-viewboxing",
            "--enable-comment-stripping",
            "--shorten-ids",
            "--create-groups",
            "--disable-style-to-xml",
        ])
        result = scourString(_read("complex-scene.svg"), options)
        expected = _read("golden-complex-maxopt.svg")
        assert result == expected
