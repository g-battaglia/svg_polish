"""Tests for svg_polish CSS parser.

Original test harness from Scour, adapted for svg_polish.
Copyright 2010 Jeff Schiller.
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import unittest

from svg_polish.css import parseCssString


class Blank(unittest.TestCase):
    def runTest(self):
        r = parseCssString("")
        self.assertEqual(len(r), 0, "Blank string returned non-empty list")
        self.assertEqual(type(r), type([]), "Blank string returned non list")


class ElementSelector(unittest.TestCase):
    def runTest(self):
        r = parseCssString("foo {}")
        self.assertEqual(len(r), 1, "Element selector not returned")
        self.assertEqual(r[0]["selector"], "foo", "Selector for foo not returned")
        self.assertEqual(len(r[0]["properties"]), 0, "Property list for foo not empty")


class ElementSelectorWithProperty(unittest.TestCase):
    def runTest(self):
        r = parseCssString("foo { bar: baz}")
        self.assertEqual(len(r), 1, "Element selector not returned")
        self.assertEqual(r[0]["selector"], "foo", "Selector for foo not returned")
        self.assertEqual(len(r[0]["properties"]), 1, "Property list for foo did not have 1")
        self.assertEqual(r[0]["properties"]["bar"], "baz", "Property bar did not have baz value")


if __name__ == "__main__":
    unittest.main()
