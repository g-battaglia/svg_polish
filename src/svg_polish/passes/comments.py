"""Strip XML comment nodes from a document.

A trivial pass: comments are removed unconditionally when the
optimizer is asked to run it. The byte saving is recorded in
``ScourStats.num_bytes_saved_in_comments`` so the report can show
how much overhead the comments contributed.

Recursion handles arbitrary depth; the function copies
``element.childNodes[:]`` before iterating because removing a child
mutates the live ``NodeList`` and would otherwise skip siblings.
"""

from __future__ import annotations

import xml.dom.minidom
from xml.dom.minidom import Document, Element

from svg_polish.stats import ScourStats

__all__ = ["remove_comments"]


def remove_comments(element: Document | Element, stats: ScourStats) -> None:
    """Remove every XML comment under *element* (in place).

    Accepts either an ``Element`` or a ``Document`` because the
    public ``scour_string`` entry point passes the parsed
    ``Document`` and recursive descent visits arbitrary node
    types via ``childNodes``. Each removed comment increments
    ``stats.num_comments_removed`` and adds its byte length to
    ``stats.num_bytes_saved_in_comments``.

    Iterates over ``element.childNodes[:]`` (a snapshot) because
    ``removeChild`` mutates the live list and otherwise we'd skip
    every other sibling.
    """
    if isinstance(element, xml.dom.minidom.Comment):
        stats.num_bytes_saved_in_comments += len(element.data)
        stats.num_comments_removed += 1
        parent = element.parentNode
        assert parent is not None
        parent.removeChild(element)
    else:
        for subelement in element.childNodes[:]:
            # childNodes' broad union confuses mypy here; the
            # isinstance dispatch above handles every concrete type.
            remove_comments(subelement, stats)  # type: ignore[arg-type]
