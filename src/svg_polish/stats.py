"""Statistics tracking for SVG optimization."""

from __future__ import annotations


class ScourStats:
    """Tracks statistics about an SVG optimization pass."""

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

    num_elements_removed: int
    num_attributes_removed: int
    num_style_properties_fixed: int
    num_bytes_saved_in_colors: int
    num_ids_removed: int
    num_comments_removed: int
    num_rasters_embedded: int
    num_path_segments_removed: int
    num_points_removed_from_polygon: int
    num_bytes_saved_in_path_data: int
    num_bytes_saved_in_comments: int
    num_bytes_saved_in_ids: int
    num_bytes_saved_in_lengths: int
    num_bytes_saved_in_transforms: int

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all statistics to zero."""
        for attr in self.__slots__:
            setattr(self, attr, 0)
