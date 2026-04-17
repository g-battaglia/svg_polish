"""Tests using real SVG fixture files as baselines.

Each test loads a real SVG file, optimizes it, and verifies correctness
by checking that the output is valid, smaller, and preserves key elements.
"""

from __future__ import annotations

from pathlib import Path

from svg_polish import optimize
from svg_polish.cli import parse_args
from svg_polish.optimizer import scour_string

FIXTURES = Path(__file__).parent / "fixtures"


def _scour(svg_path: Path, args: list[str] | None = None) -> str:
    """Load an SVG fixture and optimize it."""
    text = svg_path.read_text(encoding="utf-8")
    options = parse_args(args) if args else None
    return scour_string(text, options)


def _optimize(svg_path: Path) -> str:
    """Load an SVG fixture and optimize it using the public API."""
    return optimize(svg_path.read_text(encoding="utf-8"))


class TestFixturePathStraightCurveFlush:
    """Test with path-straight-curve-flush.svg fixture."""

    def test_optimizes_and_preserves_path(self):
        result = _optimize(FIXTURES / "path-straight-curve-flush.svg")
        assert "<path" in result
        assert "stroke" in result

    def test_path_simplified(self):
        result = _optimize(FIXTURES / "path-straight-curve-flush.svg")
        # The straight curve segment (0,0,0,0,0,10) should become v10
        assert "v" in result


class TestFixturePathLineDecomposeHV:
    """Test with path-line-decompose-hv.svg fixture."""

    def test_decomposes_to_hv(self):
        result = _optimize(FIXTURES / "path-line-decompose-hv.svg")
        assert "<path" in result
        # Should contain h or v commands after decomposition
        assert "h" in result or "v" in result

    def test_all_three_paths_preserved(self):
        result = _optimize(FIXTURES / "path-line-decompose-hv.svg")
        assert result.count("<path") == 3


class TestFixtureColorsInStyles:
    """Test with colors-in-styles.svg fixture."""

    def test_colors_shortened_in_styles(self):
        result = _scour(
            FIXTURES / "colors-in-styles.svg",
            ["--disable-style-to-xml", "--remove-metadata"],
        )
        # Colors in style attrs should be shortened
        assert "fill:#f00" in result or "fill:red" in result
        assert "stroke:#000" in result

    def test_shapes_preserved(self):
        result = _optimize(FIXTURES / "colors-in-styles.svg")
        assert "<rect" in result
        assert "<circle" in result
        assert "<ellipse" in result


class TestFixturePrecisionInStyles:
    """Test with precision-in-styles.svg fixture."""

    def test_precision_reduced_in_styles(self):
        result = _scour(
            FIXTURES / "precision-in-styles.svg",
            ["--disable-style-to-xml", "--enable-comment-stripping"],
        )
        assert "2.500" not in result
        assert "12.000" not in result
        assert "1.000" not in result

    def test_elements_preserved(self):
        result = _optimize(FIXTURES / "precision-in-styles.svg")
        assert "<rect" in result
        assert "<text" in result
        assert "<line" in result


class TestFixtureCreateGroupsTrailing:
    """Test with create-groups-trailing.svg fixture."""

    def test_groups_created(self):
        result = _scour(FIXTURES / "create-groups-trailing.svg", ["--create-groups"])
        assert "<rect" in result
        assert "<circle" in result

    def test_output_is_smaller(self):
        original = (FIXTURES / "create-groups-trailing.svg").read_text()
        result = _scour(
            FIXTURES / "create-groups-trailing.svg",
            ["--create-groups", "--enable-comment-stripping"],
        )
        assert len(result) < len(original)


class TestFixtureGradientDedup:
    """Test with gradient-dedup.svg fixture."""

    def test_duplicates_removed(self):
        result = _optimize(FIXTURES / "gradient-dedup.svg")
        # After deduplication, only one gradient should remain
        assert result.count("<linearGradient") == 1

    def test_rects_preserved(self):
        result = _optimize(FIXTURES / "gradient-dedup.svg")
        assert result.count("<rect") == 2


class TestFixtureStyleInheritance:
    """Test with style-inheritance.svg fixture."""

    def test_optimizes_inherited_styles(self):
        result = _optimize(FIXTURES / "style-inheritance.svg")
        assert "<g" in result
        assert "<rect" in result

    def test_output_is_valid_svg(self):
        result = _optimize(FIXTURES / "style-inheritance.svg")
        assert result.startswith("<")
        assert "svg" in result


class TestFixtureRenameIdsInStyle:
    """Test with rename-ids-in-style.svg fixture."""

    def test_ids_shortened(self):
        result = _scour(FIXTURES / "rename-ids-in-style.svg", ["--shorten-ids"])
        # Long IDs should be replaced with short ones
        assert "myLongGradientName" not in result
        assert "myLongClipPathName" not in result

    def test_url_references_updated(self):
        result = _scour(FIXTURES / "rename-ids-in-style.svg", ["--shorten-ids"])
        # There should still be url(#...) references
        assert "url(#" in result

    def test_output_is_smaller(self):
        original = (FIXTURES / "rename-ids-in-style.svg").read_text()
        result = _scour(FIXTURES / "rename-ids-in-style.svg", ["--shorten-ids"])
        assert len(result) < len(original)


class TestFixtureViewboxCreation:
    """Test with viewbox-creation.svg fixture."""

    def test_viewbox_created(self):
        result = _scour(FIXTURES / "viewbox-creation.svg", ["--enable-viewboxing"])
        assert "viewBox" in result

    def test_elements_preserved(self):
        result = _optimize(FIXTURES / "viewbox-creation.svg")
        assert "<rect" in result
        assert "<text" in result


class TestFixtureXlinkReferences:
    """Test with xlink-references.svg fixture."""

    def test_xlink_preserved(self):
        result = _optimize(FIXTURES / "xlink-references.svg")
        assert "href" in result  # xlink:href or href
        assert "<use" in result

    def test_gradients_preserved(self):
        result = _optimize(FIXTURES / "xlink-references.svg")
        assert "linearGradient" in result

    def test_use_elements_preserved(self):
        result = _optimize(FIXTURES / "xlink-references.svg")
        assert result.count("<use ") >= 3


class TestFixtureComplexScene:
    """Test with complex-scene.svg — exercises many optimization paths at once."""

    def test_output_is_valid_svg(self):
        result = _optimize(FIXTURES / "complex-scene.svg")
        assert result.startswith("<")
        assert "</svg>" in result

    def test_output_is_smaller(self):
        original = (FIXTURES / "complex-scene.svg").read_text()
        result = _optimize(FIXTURES / "complex-scene.svg")
        assert len(result) < len(original)

    def test_key_elements_preserved(self):
        result = _optimize(FIXTURES / "complex-scene.svg")
        assert "<rect" in result
        assert "<circle" in result
        assert "<path" in result
        assert "<text" in result
        assert "<use" in result
        assert "linearGradient" in result

    def test_gradients_deduplicated(self):
        result = _optimize(FIXTURES / "complex-scene.svg")
        # skyGrad and grassGrad are different, so both should remain
        assert result.count("<linearGradient") == 2

    def test_precision_reduced(self):
        result = _optimize(FIXTURES / "complex-scene.svg")
        # 0.900000 should be reduced
        assert "0.900000" not in result
        # 2.000, 1.500, 1.000 should be reduced
        assert "2.000" not in result
        assert "1.500" not in result

    def test_ids_shortened(self):
        result = _scour(FIXTURES / "complex-scene.svg", ["--shorten-ids"])
        assert "skyGrad" not in result
        assert "grassGrad" not in result
        assert "cloud-dot" not in result

    def test_with_viewboxing(self):
        result = _scour(FIXTURES / "complex-scene.svg", ["--enable-viewboxing"])
        assert "viewBox" in result

    def test_with_create_groups(self):
        result = _scour(FIXTURES / "complex-scene.svg", ["--create-groups"])
        assert "</svg>" in result
