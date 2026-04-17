"""Statistics tracking for SVG optimization.

This module defines :class:`ScourStats`, a counter object that tracks how
many bytes, elements, attributes, and other items were saved or modified
during an optimization run. An instance is optionally passed to
:func:`~svg_polish.optimizer.scour_string` and populated in-place as each
optimization pass runs.

The stats can be displayed to the user via the CLI ``--verbose`` flag or
inspected programmatically after calling :func:`~svg_polish.optimize_with_stats`.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["ScourStats"]


@dataclass(slots=True)
class ScourStats:
    """Tracks statistics about an SVG optimization pass.

    Every field is an integer counter that starts at zero and is incremented
    by the optimizer as it removes or simplifies data.

    **Element and attribute removal:**

        * :attr:`num_elements_removed` — SVG elements deleted entirely
          (e.g. empty ``<g>`` wrappers, invisible ``<rect>`` elements).
        * :attr:`num_attributes_removed` — Individual attributes stripped
          from elements (e.g. redundant ``fill`` values).
        * :attr:`num_ids_removed` — ``id`` attributes removed because no
          other element references them.

    **Style and color optimization:**

        * :attr:`num_style_properties_fixed` — CSS style properties repaired
          or normalised (e.g. ``style="fill: black;"`` → ``fill="black"``).
        * :attr:`num_bytes_saved_in_colors` — Bytes saved by shortening color
          values (e.g. ``"#ff0000"`` → ``"red"``, ``"#aabbcc"`` → ``"#abc"``).

    **Path and geometry optimization:**

        * :attr:`num_path_segments_removed` — Path segments eliminated
          (e.g. consecutive identical lineto commands merged).
        * :attr:`num_points_removed_from_polygon` — Polygon points eliminated
          (e.g. collinear intermediate points).
        * :attr:`num_bytes_saved_in_path_data` — Bytes saved by rewriting
          path data more compactly (coordinate shortening, command merging).

    **Length and transform optimization:**

        * :attr:`num_bytes_saved_in_lengths` — Bytes saved by shortening
          length values (e.g. ``"0.000"`` → ``"0"``, ``"12.00"`` → ``"12"``).
        * :attr:`num_bytes_saved_in_transforms` — Bytes saved by simplifying
          transform strings (e.g. ``"translate(0,0)"`` → removed).

    **Other:**

        * :attr:`num_comments_removed` — XML comments stripped from the output.
        * :attr:`num_bytes_saved_in_comments` — Bytes saved by removing comments.
        * :attr:`num_rasters_embedded` — Raster images that were base64-encoded
          and embedded inline (when the relevant option is enabled).

    Uses ``slots=True`` for memory efficiency since many optimization passes
    increment these counters thousands of times on large files.
    """

    num_elements_removed: int = 0
    """SVG elements removed entirely."""

    num_attributes_removed: int = 0
    """Individual attributes stripped from elements."""

    num_style_properties_fixed: int = 0
    """CSS style properties repaired or inlined."""

    num_bytes_saved_in_colors: int = 0
    """Bytes saved by shortening color values."""

    num_ids_removed: int = 0
    """``id`` attributes removed because unreferenced."""

    num_comments_removed: int = 0
    """XML comments removed."""

    num_rasters_embedded: int = 0
    """Raster images base64-encoded and embedded inline."""

    num_path_segments_removed: int = 0
    """Path segments eliminated."""

    num_points_removed_from_polygon: int = 0
    """Polygon points eliminated (e.g. collinear)."""

    num_bytes_saved_in_path_data: int = 0
    """Bytes saved by rewriting path data more compactly."""

    num_bytes_saved_in_comments: int = 0
    """Bytes saved by removing XML comments."""

    num_bytes_saved_in_ids: int = 0
    """Bytes saved by shortening or removing id values."""

    num_bytes_saved_in_lengths: int = 0
    """Bytes saved by shortening length values."""

    num_bytes_saved_in_transforms: int = 0
    """Bytes saved by simplifying transform strings."""

    @property
    def total_bytes_saved(self) -> int:
        """Sum of every ``num_bytes_saved_in_*`` counter.

        Useful for a single headline number when reporting; individual
        counters remain available for granular breakdowns.
        """
        return (
            self.num_bytes_saved_in_colors
            + self.num_bytes_saved_in_path_data
            + self.num_bytes_saved_in_comments
            + self.num_bytes_saved_in_ids
            + self.num_bytes_saved_in_lengths
            + self.num_bytes_saved_in_transforms
        )

    def reset(self) -> None:
        """Reset all statistics counters to zero.

        Iterates over the dataclass fields so adding a new counter
        automatically includes it here — no need to update this method.
        """
        for field in fields(self):
            setattr(self, field.name, 0)
