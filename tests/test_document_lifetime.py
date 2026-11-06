"""Optimization must release its XML tree without waiting for cyclic GC."""

from __future__ import annotations

import gc
import weakref

import pytest

from svg_polish import optimizer
from svg_polish.constants import NS
from svg_polish.dom import _set_xlink_href

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="20"/></svg>'


def test_completed_document_is_released_even_with_cyclic_gc_disabled(monkeypatch):
    references = []
    parse = optimizer._parse_xml

    def observe(*args, **kwargs):
        document = parse(*args, **kwargs)
        references.append(weakref.ref(document))
        return document

    monkeypatch.setattr(optimizer, "_parse_xml", observe)
    enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(12):
            assert "<rect" in optimizer.scour_string(SVG)
        assert all(reference() is None for reference in references)
    finally:
        if enabled:
            gc.enable()


def test_failed_pass_also_unlinks_owned_document(monkeypatch):
    documents = []

    def fail(document, options, stats):
        documents.append(document)
        raise RuntimeError("pass failure")

    monkeypatch.setattr(optimizer, "_optimize_document", fail)
    with pytest.raises(RuntimeError, match="pass failure"):
        optimizer.scour_string(SVG)
    assert len(documents) == 1
    assert not documents[0].childNodes
    assert documents[0].documentElement is None


def test_rewritten_xlink_attribute_keeps_both_dom_indexes_consistent():
    from xml.dom.minidom import parseString

    with parseString('<svg xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="#old"/></svg>') as document:
        use = document.getElementsByTagName("use")[0]
        _set_xlink_href(use, "#new")
        assert use.getAttribute("href") == "#new"
        assert use.getAttributeNS(NS["XLINK"], "href") == "#new"
        assert use.getAttributeNode("xlink:href") is None
        # Context exit must unlink the document without KeyError.
