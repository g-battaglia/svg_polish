"""Minimal CSS parser for SVG ``<style>`` element analysis.

This module implements *yocto-css*, an extremely small CSS parser that extracts
rules from CSS text found inside SVG ``<style>`` elements.  It is intentionally
minimal — it handles only the flat ``selector { property: value; … }`` syntax
that appears in typical inline SVG stylesheets.  It does **not** support
at-rules (``@media``, ``@import``, etc.), nested selectors, or comments.

The parser is used during optimization to inspect CSS rules that reference SVG
elements by ID (e.g. ``fill: url(#gradient1)``) so that those IDs are not
stripped as unused.

Original copyright:
    Copyright 2009 Jeff Schiller
    Part of Scour (http://www.codedread.com/scour/)
    Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from typing import TypedDict


class CSSRule(TypedDict):
    """A single parsed CSS rule.

    Attributes:
        selector: The CSS selector string (e.g. ``".my-class"`` or ``"#myId"``).
        properties: A dict mapping CSS property names to their values
            (e.g. ``{"fill": "red", "stroke": "blue"}``).
    """

    selector: str
    properties: dict[str, str]


def parseCssString(css_text: str) -> list[CSSRule]:
    """Parse a CSS string into a list of rules.

    Splits the input on ``}`` to isolate rule blocks, then splits each block
    on ``{`` to separate the selector from the declaration block.  Individual
    declarations are split on ``;`` and then on ``:`` to extract property–value
    pairs.

    Malformed input (unmatched braces, missing colons, etc.) is silently
    skipped rather than raising an error — this keeps the parser robust when
    fed the variety of CSS found in real-world SVG files.

    Args:
        css_text: The raw CSS text, typically the text content of an SVG
            ``<style>`` element.

    Returns:
        A list of :class:`CSSRule` dicts.  Returns an empty list for blank
        or entirely malformed input.

    Example::

        >>> parseCssString('.cls1{fill:red;stroke:blue}')
        [{'selector': '.cls1', 'properties': {'fill': 'red', 'stroke': 'blue'}}]
    """
    rules: list[CSSRule] = []
    # Split on closing brace — each chunk is either a "selector { declarations" pair
    # or trailing whitespace/empty string after the last rule.
    chunks = css_text.split("}")
    for chunk in chunks:
        bits = chunk.split("{")
        if len(bits) != 2:
            continue
        selector = bits[0].strip()
        # Split declaration block on semicolons into individual property: value pairs.
        bites = bits[1].strip().split(";")
        if len(bites) < 1:  # pragma: no cover — str.split() always returns >= 1 element
            continue
        props: dict[str, str] = {}
        for bite in bites:
            nibbles = bite.strip().split(":")
            if len(nibbles) != 2:
                continue
            props[nibbles[0].strip()] = nibbles[1].strip()
        # Only emit a rule with its selector and parsed properties.
        rules.append(CSSRule(selector=selector, properties=props))
    return rules
