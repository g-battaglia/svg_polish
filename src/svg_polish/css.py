"""Minimal CSS parser for SVG style analysis.

yocto-css: an extremely bare minimum CSS parser.

Original copyright:
    Copyright 2009 Jeff Schiller
    Part of Scour (http://www.codedread.com/scour/)
    Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from typing import TypedDict


class CSSRule(TypedDict):
    """A single CSS rule with selector and properties."""

    selector: str
    properties: dict[str, str]


def parseCssString(css_text: str) -> list[CSSRule]:
    """Parse a CSS string into a list of rules.

    Each rule is a dictionary with ``selector`` and ``properties`` keys.

    Args:
        css_text: The CSS text to parse.

    Returns:
        A list of CSS rules.
    """
    rules: list[CSSRule] = []
    chunks = css_text.split("}")
    for chunk in chunks:
        bits = chunk.split("{")
        if len(bits) != 2:
            continue
        selector = bits[0].strip()
        bites = bits[1].strip().split(";")
        if len(bites) < 1:
            continue
        props: dict[str, str] = {}
        for bite in bites:
            nibbles = bite.strip().split(":")
            if len(nibbles) != 2:
                continue
            props[nibbles[0].strip()] = nibbles[1].strip()
        rules.append(CSSRule(selector=selector, properties=props))
    return rules
