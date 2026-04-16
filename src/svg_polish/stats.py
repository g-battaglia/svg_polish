"""Statistics tracking for SVG optimization.

This module defines :class:`ScourStats`, a lightweight counter object that
tracks how many bytes, elements, attributes, and other items were saved or
modified during an optimization run.  An instance is optionally passed to
:func:`~svg_polish.optimizer.scourString` and populated in-place as each
optimization pass runs.

The stats can be displayed to the user via the CLI ``--verbose`` flag or
inspected programmatically after calling :func:`~svg_polish.optimize`.
"""

from __future__ import annotations


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

    Uses ``__slots__`` for memory efficiency since many optimization passes
    increment these counters thousands of times on large files.
    """

    __slots__ = (
        "num_elements_removed",
        "num_attributes_removed",
        "num_style_properties_fixed",
        "num_bytes_saved_in_colors",
        "num_ids_removed",
        "num_comments_removed",
        "num_rasters_embedded",
        "num_path_segments_removed",
        "num_points_removed_from_polygon",
        "num_bytes_saved_in_path_data",
        "num_bytes_saved_in_comments",
        "num_bytes_saved_in_ids",
        "num_bytes_saved_in_lengths",
        "num_bytes_saved_in_transforms",
    )

    # -- Element & attribute removal counters --
    num_elements_removed: int
    """SVG elements removed entirely."""
    num_attributes_removed: int
    """Individual attributes stripped from elements."""
    num_ids_removed: int
    """``id`` attributes removed because unreferenced."""

    # -- Style & color counters --
    num_style_properties_fixed: int
    """CSS style properties repaired or inlined."""
    num_bytes_saved_in_colors: int
    """Bytes saved by shortening color values."""

    # -- Path & geometry counters --
    num_path_segments_removed: int
    """Path segments eliminated."""
    num_points_removed_from_polygon: int
    """Polygon points eliminated (e.g. collinear)."""
    num_bytes_saved_in_path_data: int
    """Bytes saved by rewriting path data more compactly."""

    # -- Length & transform counters --
    num_bytes_saved_in_lengths: int
    """Bytes saved by shortening length values."""
    num_bytes_saved_in_transforms: int
    """Bytes saved by simplifying transform strings."""

    # -- Other counters --
    num_comments_removed: int
    """XML comments removed."""
    num_bytes_saved_in_comments: int
    """Bytes saved by removing XML comments."""
    num_rasters_embedded: int
    """Raster images base64-encoded and embedded inline."""

    # NOTE: num_bytes_saved_in_ids is tracked in __slots__ but was a legacy
    # field — it is kept for API compatibility.
    num_bytes_saved_in_ids: int
    """Bytes saved by shortening or removing id values."""

    def __init__(self) -> None:
        """Initialise every counter to ``0`` via :meth:`reset`.

        ``__slots__`` is enumerated dynamically, so newly added counters do
        not require updating this constructor.
        """
        self.reset()

    def reset(self) -> None:
        """Reset all statistics counters to zero.

        Iterates over :attr:`__slots__` so that adding a new slot
        automatically includes it here — no need to update this method.
        """
        for attr in self.__slots__:
            setattr(self, attr, 0)
