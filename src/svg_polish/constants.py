"""SVG constants, namespaces, named colors, default property values, and attribute tables.

This module contains all the static data used by the SVG optimizer.
It is imported at startup and never modified at runtime.

Contents:
    - Application identity (APP, VER, COPYRIGHT)
    - XML entity escape maps
    - Compiled regex patterns
    - SVG/editor XML namespace URIs
    - SVG presentation attribute names
    - Named CSS/SVG color table
    - CSS/SVG default property values
    - SVG attribute reference-tracking set
    - Text content element names
    - Default attribute specification table
    - Canonical attribute ordering
"""

from __future__ import annotations

import re
from collections import defaultdict, namedtuple

from svg_polish import __version__  # noqa: I001 — must import before using __version__ below

# =============================================================================
# Application Identity and Version
# =============================================================================

APP = "svg-polish"
VER = __version__
COPYRIGHT = "Copyright Jeff Schiller, Louis Simard, 2010"


# =============================================================================
# XML Entity Escape Maps
# =============================================================================

# XML entity escape maps for make_well_formed().
# Each map contains only the entities that need escaping for a given quote style.
# Used by serializeXML() to escape attribute values and text content.
XML_ENTS_NO_QUOTES: dict[str, str] = {"<": "&lt;", ">": "&gt;", "&": "&amp;"}
XML_ENTS_ESCAPE_APOS: dict[str, str] = XML_ENTS_NO_QUOTES.copy()
XML_ENTS_ESCAPE_APOS["'"] = "&apos;"
XML_ENTS_ESCAPE_QUOT: dict[str, str] = XML_ENTS_NO_QUOTES.copy()
XML_ENTS_ESCAPE_QUOT['"'] = "&quot;"


# =============================================================================
# Compiled Regular Expressions
# =============================================================================

# Regex: split on comma-or-whitespace (SVG coordinate lists).
# Matches "x y", "x,y", or mixed whitespace/comma separators.
RE_COMMA_WSP: re.Pattern[str] = re.compile(r"\s*[\s,]\s*")
# Regex: collapse multiple spaces to one (used in text content normalization).
_RE_MULTI_SPACE: re.Pattern[str] = re.compile(r"  +")

# Regex: parse rgb(R, G, B) color strings (integer 0-255 per channel).
rgb: re.Pattern[str] = re.compile(r"\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*")
# Regex: parse rgb(R%, G%, B%) color strings (percentage per channel).
rgbp: re.Pattern[str] = re.compile(r"\s*rgb\(\s*(\d*\.?\d+)%\s*,\s*(\d*\.?\d+)%\s*,\s*(\d*\.?\d+)%\s*\)\s*")

# Regex: SVG length string components.
# scinumber matches scientific notation like "1.5e-3".
scinumber: re.Pattern[str] = re.compile(r"[-+]?(\d*\.?)?\d+[eE][-+]?\d+")
# number matches plain decimal numbers like "1.5" or "42".
number: re.Pattern[str] = re.compile(r"[-+]?(\d*\.?)?\d+")
# sciExponent extracts the exponent part from scientific notation.
sciExponent: re.Pattern[str] = re.compile(r"[eE]([-+]?\d+)")
# unit matches SVG unit suffixes (em, ex, px, pt, pc, cm, mm, in, %).
unit: re.Pattern[str] = re.compile("(em|ex|px|pt|pc|cm|mm|in|%){1,1}$")


# =============================================================================
# SVG Length Units
# =============================================================================


class Unit:
    """Integer constants and lookup tables for SVG length units.

    Provides bidirectional mapping between unit strings (``"px"``, ``"%"``,
    ``"em"``, etc.) and their integer constants.  Used by :class:`SVGLength`
    to parse and serialize length values.
    """

    INVALID = -1
    NONE = 0
    PCT = 1
    PX = 2
    PT = 3
    PC = 4
    EM = 5
    EX = 6
    CM = 7
    MM = 8
    IN = 9

    # String-to-unit mapping.  Converts unit strings to their integer constants.
    s2u: dict[str, int] = {
        "": NONE,
        "%": PCT,
        "px": PX,
        "pt": PT,
        "pc": PC,
        "em": EM,
        "ex": EX,
        "cm": CM,
        "mm": MM,
        "in": IN,
    }

    # Unit-to-string mapping.  Converts unit integer constants to their strings.
    u2s: dict[int, str] = {
        NONE: "",
        PCT: "%",
        PX: "px",
        PT: "pt",
        PC: "pc",
        EM: "em",
        EX: "ex",
        CM: "cm",
        MM: "mm",
        IN: "in",
    }

    @staticmethod
    def get(unitstr: str | None) -> int:
        """Convert a unit string (e.g. ``"px"``, ``"%"``) to its integer constant.

        Returns :attr:`INVALID` for unknown strings and :attr:`NONE` for ``None``.
        """
        if unitstr is None:
            return Unit.NONE
        try:
            return Unit.s2u[unitstr]
        except KeyError:
            return Unit.INVALID

    @staticmethod
    def str(unitint: int) -> str:
        """Convert a unit integer constant to its string form.

        Returns ``"INVALID"`` for unknown constants.
        """
        try:
            return Unit.u2s[unitint]
        except KeyError:
            return "INVALID"


# =============================================================================
# XML and SVG Namespace Constants
# =============================================================================

# SVG and editor-specific XML namespace URIs.
# Used to identify/strip editor-specific elements and attributes.
# Key = short name (str), Value = namespace URI (str).
NS: dict[str, str] = {
    "SVG": "http://www.w3.org/2000/svg",
    "XLINK": "http://www.w3.org/1999/xlink",
    "SODIPODI": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "INKSCAPE": "http://www.inkscape.org/namespaces/inkscape",
    "ADOBE_ILLUSTRATOR": "http://ns.adobe.com/AdobeIllustrator/10.0/",
    "ADOBE_GRAPHS": "http://ns.adobe.com/Graphs/1.0/",
    "ADOBE_SVG_VIEWER": "http://ns.adobe.com/AdobeSVGViewerExtensions/3.0/",
    "ADOBE_VARIABLES": "http://ns.adobe.com/Variables/1.0/",
    "ADOBE_SFW": "http://ns.adobe.com/SaveForWeb/1.0/",
    "ADOBE_EXTENSIBILITY": "http://ns.adobe.com/Extensibility/1.0/",
    "ADOBE_FLOWS": "http://ns.adobe.com/Flows/1.0/",
    "ADOBE_IMAGE_REPLACEMENT": "http://ns.adobe.com/ImageReplacement/1.0/",
    "ADOBE_CUSTOM": "http://ns.adobe.com/GenericCustomNamespace/1.0/",
    "ADOBE_XPATH": "http://ns.adobe.com/XPath/1.0/",
    "SKETCH": "http://www.bohemiancoding.com/sketch/ns",
}

# Namespace URIs of editor-specific elements/attributes to strip by default.
# These are Inkscape, Sodipodi, Adobe Illustrator, Sketch, and related tools.
# Unless --keep-editor-data is set, elements/attributes in these namespaces are removed.
unwanted_ns: list[str] = [
    NS["SODIPODI"],
    NS["INKSCAPE"],
    NS["ADOBE_ILLUSTRATOR"],
    NS["ADOBE_GRAPHS"],
    NS["ADOBE_SVG_VIEWER"],
    NS["ADOBE_VARIABLES"],
    NS["ADOBE_SFW"],
    NS["ADOBE_EXTENSIBILITY"],
    NS["ADOBE_FLOWS"],
    NS["ADOBE_IMAGE_REPLACEMENT"],
    NS["ADOBE_CUSTOM"],
    NS["ADOBE_XPATH"],
    NS["SKETCH"],
]


# =============================================================================
# SVG Presentation Attributes
# =============================================================================

# Complete set of SVG presentation attributes (CSS property names usable as XML attributes).
# Stored as frozenset for O(1) membership testing in repairStyle() and style-to-XML conversion.
#
# Sources:
#     https://www.w3.org/TR/SVG/propidx.html              (SVG 1.1 — implemented)
#     https://www.w3.org/TR/SVGTiny12/attributeTable.html  (SVG 1.2 Tiny — implemented)
#     https://www.w3.org/TR/SVG2/propidx.html              (SVG 2 — not yet implemented)
svgAttributes: frozenset[str] = frozenset(
    [
        # SVG 1.1
        "alignment-baseline",
        "baseline-shift",
        "clip",
        "clip-path",
        "clip-rule",
        "color",
        "color-interpolation",
        "color-interpolation-filters",
        "color-profile",
        "color-rendering",
        "cursor",
        "direction",
        "display",
        "dominant-baseline",
        "enable-background",
        "fill",
        "fill-opacity",
        "fill-rule",
        "filter",
        "flood-color",
        "flood-opacity",
        "font",
        "font-family",
        "font-size",
        "font-size-adjust",
        "font-stretch",
        "font-style",
        "font-variant",
        "font-weight",
        "glyph-orientation-horizontal",
        "glyph-orientation-vertical",
        "image-rendering",
        "kerning",
        "letter-spacing",
        "lighting-color",
        "marker",
        "marker-end",
        "marker-mid",
        "marker-start",
        "mask",
        "opacity",
        "overflow",
        "pointer-events",
        "shape-rendering",
        "stop-color",
        "stop-opacity",
        "stroke",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-width",
        "text-anchor",
        "text-decoration",
        "text-rendering",
        "unicode-bidi",
        "visibility",
        "word-spacing",
        "writing-mode",
        # SVG 1.2 Tiny
        "audio-level",
        "buffered-rendering",
        "display-align",
        "line-increment",
        "solid-color",
        "solid-opacity",
        "text-align",
        "vector-effect",
        "viewport-fill",
        "viewport-fill-opacity",
    ]
)


# =============================================================================
# Named CSS Colors
# =============================================================================

# Named CSS/SVG colors mapped to their rgb() equivalents.
# Key = lowercase color name (str), Value = "rgb(R, G, B)" string.
# Source: https://www.w3.org/TR/SVG/types.html#ColorKeywords
# Used by convertColor() as input; _name_to_hex (below) is the pre-computed hex form.
colors: dict[str, str] = {
    "aliceblue": "rgb(240, 248, 255)",
    "antiquewhite": "rgb(250, 235, 215)",
    "aqua": "rgb( 0, 255, 255)",
    "aquamarine": "rgb(127, 255, 212)",
    "azure": "rgb(240, 255, 255)",
    "beige": "rgb(245, 245, 220)",
    "bisque": "rgb(255, 228, 196)",
    "black": "rgb( 0, 0, 0)",
    "blanchedalmond": "rgb(255, 235, 205)",
    "blue": "rgb( 0, 0, 255)",
    "blueviolet": "rgb(138, 43, 226)",
    "brown": "rgb(165, 42, 42)",
    "burlywood": "rgb(222, 184, 135)",
    "cadetblue": "rgb( 95, 158, 160)",
    "chartreuse": "rgb(127, 255, 0)",
    "chocolate": "rgb(210, 105, 30)",
    "coral": "rgb(255, 127, 80)",
    "cornflowerblue": "rgb(100, 149, 237)",
    "cornsilk": "rgb(255, 248, 220)",
    "crimson": "rgb(220, 20, 60)",
    "cyan": "rgb( 0, 255, 255)",
    "darkblue": "rgb( 0, 0, 139)",
    "darkcyan": "rgb( 0, 139, 139)",
    "darkgoldenrod": "rgb(184, 134, 11)",
    "darkgray": "rgb(169, 169, 169)",
    "darkgreen": "rgb( 0, 100, 0)",
    "darkgrey": "rgb(169, 169, 169)",
    "darkkhaki": "rgb(189, 183, 107)",
    "darkmagenta": "rgb(139, 0, 139)",
    "darkolivegreen": "rgb( 85, 107, 47)",
    "darkorange": "rgb(255, 140, 0)",
    "darkorchid": "rgb(153, 50, 204)",
    "darkred": "rgb(139, 0, 0)",
    "darksalmon": "rgb(233, 150, 122)",
    "darkseagreen": "rgb(143, 188, 143)",
    "darkslateblue": "rgb( 72, 61, 139)",
    "darkslategray": "rgb( 47, 79, 79)",
    "darkslategrey": "rgb( 47, 79, 79)",
    "darkturquoise": "rgb( 0, 206, 209)",
    "darkviolet": "rgb(148, 0, 211)",
    "deeppink": "rgb(255, 20, 147)",
    "deepskyblue": "rgb( 0, 191, 255)",
    "dimgray": "rgb(105, 105, 105)",
    "dimgrey": "rgb(105, 105, 105)",
    "dodgerblue": "rgb( 30, 144, 255)",
    "firebrick": "rgb(178, 34, 34)",
    "floralwhite": "rgb(255, 250, 240)",
    "forestgreen": "rgb( 34, 139, 34)",
    "fuchsia": "rgb(255, 0, 255)",
    "gainsboro": "rgb(220, 220, 220)",
    "ghostwhite": "rgb(248, 248, 255)",
    "gold": "rgb(255, 215, 0)",
    "goldenrod": "rgb(218, 165, 32)",
    "gray": "rgb(128, 128, 128)",
    "grey": "rgb(128, 128, 128)",
    "green": "rgb( 0, 128, 0)",
    "greenyellow": "rgb(173, 255, 47)",
    "honeydew": "rgb(240, 255, 240)",
    "hotpink": "rgb(255, 105, 180)",
    "indianred": "rgb(205, 92, 92)",
    "indigo": "rgb( 75, 0, 130)",
    "ivory": "rgb(255, 255, 240)",
    "khaki": "rgb(240, 230, 140)",
    "lavender": "rgb(230, 230, 250)",
    "lavenderblush": "rgb(255, 240, 245)",
    "lawngreen": "rgb(124, 252, 0)",
    "lemonchiffon": "rgb(255, 250, 205)",
    "lightblue": "rgb(173, 216, 230)",
    "lightcoral": "rgb(240, 128, 128)",
    "lightcyan": "rgb(224, 255, 255)",
    "lightgoldenrodyellow": "rgb(250, 250, 210)",
    "lightgray": "rgb(211, 211, 211)",
    "lightgreen": "rgb(144, 238, 144)",
    "lightgrey": "rgb(211, 211, 211)",
    "lightpink": "rgb(255, 182, 193)",
    "lightsalmon": "rgb(255, 160, 122)",
    "lightseagreen": "rgb( 32, 178, 170)",
    "lightskyblue": "rgb(135, 206, 250)",
    "lightslategray": "rgb(119, 136, 153)",
    "lightslategrey": "rgb(119, 136, 153)",
    "lightsteelblue": "rgb(176, 196, 222)",
    "lightyellow": "rgb(255, 255, 224)",
    "lime": "rgb( 0, 255, 0)",
    "limegreen": "rgb( 50, 205, 50)",
    "linen": "rgb(250, 240, 230)",
    "magenta": "rgb(255, 0, 255)",
    "maroon": "rgb(128, 0, 0)",
    "mediumaquamarine": "rgb(102, 205, 170)",
    "mediumblue": "rgb( 0, 0, 205)",
    "mediumorchid": "rgb(186, 85, 211)",
    "mediumpurple": "rgb(147, 112, 219)",
    "mediumseagreen": "rgb( 60, 179, 113)",
    "mediumslateblue": "rgb(123, 104, 238)",
    "mediumspringgreen": "rgb( 0, 250, 154)",
    "mediumturquoise": "rgb( 72, 209, 204)",
    "mediumvioletred": "rgb(199, 21, 133)",
    "midnightblue": "rgb( 25, 25, 112)",
    "mintcream": "rgb(245, 255, 250)",
    "mistyrose": "rgb(255, 228, 225)",
    "moccasin": "rgb(255, 228, 181)",
    "navajowhite": "rgb(255, 222, 173)",
    "navy": "rgb( 0, 0, 128)",
    "oldlace": "rgb(253, 245, 230)",
    "olive": "rgb(128, 128, 0)",
    "olivedrab": "rgb(107, 142, 35)",
    "orange": "rgb(255, 165, 0)",
    "orangered": "rgb(255, 69, 0)",
    "orchid": "rgb(218, 112, 214)",
    "palegoldenrod": "rgb(238, 232, 170)",
    "palegreen": "rgb(152, 251, 152)",
    "paleturquoise": "rgb(175, 238, 238)",
    "palevioletred": "rgb(219, 112, 147)",
    "papayawhip": "rgb(255, 239, 213)",
    "peachpuff": "rgb(255, 218, 185)",
    "peru": "rgb(205, 133, 63)",
    "pink": "rgb(255, 192, 203)",
    "plum": "rgb(221, 160, 221)",
    "powderblue": "rgb(176, 224, 230)",
    "purple": "rgb(128, 0, 128)",
    "red": "rgb(255, 0, 0)",
    "rosybrown": "rgb(188, 143, 143)",
    "royalblue": "rgb( 65, 105, 225)",
    "saddlebrown": "rgb(139, 69, 19)",
    "salmon": "rgb(250, 128, 114)",
    "sandybrown": "rgb(244, 164, 96)",
    "seagreen": "rgb( 46, 139, 87)",
    "seashell": "rgb(255, 245, 238)",
    "sienna": "rgb(160, 82, 45)",
    "silver": "rgb(192, 192, 192)",
    "skyblue": "rgb(135, 206, 235)",
    "slateblue": "rgb(106, 90, 205)",
    "slategray": "rgb(112, 128, 144)",
    "slategrey": "rgb(112, 128, 144)",
    "snow": "rgb(255, 250, 250)",
    "springgreen": "rgb( 0, 255, 127)",
    "steelblue": "rgb( 70, 130, 180)",
    "tan": "rgb(210, 180, 140)",
    "teal": "rgb( 0, 128, 128)",
    "thistle": "rgb(216, 191, 216)",
    "tomato": "rgb(255, 99, 71)",
    "turquoise": "rgb( 64, 224, 208)",
    "violet": "rgb(238, 130, 238)",
    "wheat": "rgb(245, 222, 179)",
    "white": "rgb(255, 255, 255)",
    "whitesmoke": "rgb(245, 245, 245)",
    "yellow": "rgb(255, 255, 0)",
    "yellowgreen": "rgb(154, 205, 50)",
}


# =============================================================================
# Pre-computed Color Hex Mapping
# =============================================================================

# Pre-computed name->shortest-hex mapping, built at import time from `colors` dict.
# Key = lowercase color name (str), Value = shortest hex form (e.g. "#fff" or "#abcd").
# Avoids regex parsing in the hot convertColor() path for all 148 named colors.
_name_to_hex: dict[str, str] = {}
for _name, _rgb_str in colors.items():
    _m = rgb.match(_rgb_str)
    if _m:
        _r, _g, _b = int(_m.group(1)), int(_m.group(2)), int(_m.group(3))
        _hex = f"#{_r:02x}{_g:02x}{_b:02x}"
        # Compress to 3-char shorthand if all channels have matching hex digits
        # (e.g. "#aabbcc" -> "#abc", "#ffffff" -> "#fff").
        if len(_hex) == 7 and _hex[1] == _hex[2] and _hex[3] == _hex[4] and _hex[5] == _hex[6]:
            _hex = "#" + _hex[1] + _hex[3] + _hex[5]
        _name_to_hex[_name] = _hex


# =============================================================================
# CSS/SVG Default Property Values
# =============================================================================

# CSS/SVG default property values that can safely be removed from elements.
# Key = property name (str), Value = default value (str).
# Excludes all properties with 'auto' as default (too ambiguous to remove).
# Used by removeDefaultAttributeValues() to strip redundant attributes/styles.
#
# Sources:
#     https://www.w3.org/TR/SVG/propidx.html              (SVG 1.1)
#     https://www.w3.org/TR/SVGTiny12/attributeTable.html  (SVG 1.2 Tiny)
#     https://www.w3.org/TR/SVG2/propidx.html              (SVG 2 — not yet implemented)
default_properties: dict[str, str] = {  # excluded all properties with 'auto' as default
    # SVG 1.1 presentation attributes
    "baseline-shift": "baseline",
    "clip-path": "none",
    "clip-rule": "nonzero",
    "color": "#000",
    "color-interpolation-filters": "linearRGB",
    "color-interpolation": "sRGB",
    "direction": "ltr",
    "display": "inline",
    "enable-background": "accumulate",
    "fill": "#000",
    "fill-opacity": "1",
    "fill-rule": "nonzero",
    "filter": "none",
    "flood-color": "#000",
    "flood-opacity": "1",
    "font-size-adjust": "none",
    "font-size": "medium",
    "font-stretch": "normal",
    "font-style": "normal",
    "font-variant": "normal",
    "font-weight": "normal",
    "glyph-orientation-horizontal": "0deg",
    "letter-spacing": "normal",
    "lighting-color": "#fff",
    "marker": "none",
    "marker-start": "none",
    "marker-mid": "none",
    "marker-end": "none",
    "mask": "none",
    "opacity": "1",
    "pointer-events": "visiblePainted",
    "stop-color": "#000",
    "stop-opacity": "1",
    "stroke": "none",
    "stroke-dasharray": "none",
    "stroke-dashoffset": "0",
    "stroke-linecap": "butt",
    "stroke-linejoin": "miter",
    "stroke-miterlimit": "4",
    "stroke-opacity": "1",
    "stroke-width": "1",
    "text-anchor": "start",
    "text-decoration": "none",
    "unicode-bidi": "normal",
    "visibility": "visible",
    "word-spacing": "normal",
    "writing-mode": "lr-tb",
    # SVG 1.2 tiny properties
    "audio-level": "1",
    "solid-color": "#000",
    "solid-opacity": "1",
    "text-align": "start",
    "vector-effect": "none",
    "viewport-fill": "none",
    "viewport-fill-opacity": "1",
}


# =============================================================================
# SVG Reference-Tracking Attributes
# =============================================================================

# SVG attributes that may contain url(#id) references to other elements.
# Frozen for O(1) membership testing during DOM traversal.
# Used by findReferencingProperty() and findReferencedElements().
referencingProps: frozenset[str] = frozenset(
    ["fill", "stroke", "filter", "clip-path", "mask", "marker-start", "marker-end", "marker-mid"]
)


# =============================================================================
# Text Content Elements
# =============================================================================

# SVG elements whose text content is significant (whitespace must be preserved).
# Inside these elements, serializeXML() does not add indentation or strip whitespace.
# Source: https://www.w3.org/TR/SVG/text.html#WhiteSpace
TEXT_CONTENT_ELEMENTS: frozenset[str] = frozenset(
    [
        "text",
        "tspan",
        "tref",
        "textPath",
        "altGlyph",
        "flowDiv",
        "flowPara",
        "flowSpan",
        "flowTref",
        "flowLine",
    ]
)


# =============================================================================
# Default Attribute Specification Table
# =============================================================================

# Named tuple representing a default attribute rule.
# Fields:
#   name (str):       attribute name
#   value:            default value (str for text, int/float for numeric)
#   units (int):      expected Unit constant (None for text values)
#   elements (list):  element tag names this rule applies to (None = all)
#   conditions:       optional callable(node) -> bool; rule applies only when True
DefaultAttribute = namedtuple("DefaultAttribute", ["name", "value", "units", "elements", "conditions"])
DefaultAttribute.__new__.__defaults__ = (None,) * len(DefaultAttribute._fields)

# Table of SVG attributes with known default values that can be safely removed.
# Used by removeDefaultAttributeValues() and removeDefaultAttributeValue().
# Each entry specifies: attribute name, default value, expected unit, applicable elements, and
# optional conditions that must be met for the default to apply.
default_attributes: list[DefaultAttribute] = [
    # unit systems
    DefaultAttribute("clipPathUnits", "userSpaceOnUse", elements=["clipPath"]),
    DefaultAttribute("filterUnits", "objectBoundingBox", elements=["filter"]),
    DefaultAttribute("gradientUnits", "objectBoundingBox", elements=["linearGradient", "radialGradient"]),
    DefaultAttribute("maskUnits", "objectBoundingBox", elements=["mask"]),
    DefaultAttribute("maskContentUnits", "userSpaceOnUse", elements=["mask"]),
    DefaultAttribute("patternUnits", "objectBoundingBox", elements=["pattern"]),
    DefaultAttribute("patternContentUnits", "userSpaceOnUse", elements=["pattern"]),
    DefaultAttribute("primitiveUnits", "userSpaceOnUse", elements=["filter"]),
    DefaultAttribute(
        "externalResourcesRequired",
        "false",
        elements=[
            "a",
            "altGlyph",
            "animate",
            "animateColor",
            "animateMotion",
            "animateTransform",
            "circle",
            "clipPath",
            "cursor",
            "defs",
            "ellipse",
            "feImage",
            "filter",
            "font",
            "foreignObject",
            "g",
            "image",
            "line",
            "linearGradient",
            "marker",
            "mask",
            "mpath",
            "path",
            "pattern",
            "polygon",
            "polyline",
            "radialGradient",
            "rect",
            "script",
            "set",
            "svg",
            "switch",
            "symbol",
            "text",
            "textPath",
            "tref",
            "tspan",
            "use",
            "view",
        ],
    ),
    # svg elements
    DefaultAttribute("width", 100, Unit.PCT, elements=["svg"]),
    DefaultAttribute("height", 100, Unit.PCT, elements=["svg"]),
    DefaultAttribute("baseProfile", "none", elements=["svg"]),
    DefaultAttribute(
        "preserveAspectRatio",
        "xMidYMid meet",
        elements=["feImage", "image", "marker", "pattern", "svg", "symbol", "view"],
    ),
    # common attributes / basic types
    DefaultAttribute(
        "x",
        0,
        elements=[
            "cursor",
            "fePointLight",
            "feSpotLight",
            "foreignObject",
            "image",
            "pattern",
            "rect",
            "svg",
            "text",
            "use",
        ],
    ),
    DefaultAttribute(
        "y",
        0,
        elements=[
            "cursor",
            "fePointLight",
            "feSpotLight",
            "foreignObject",
            "image",
            "pattern",
            "rect",
            "svg",
            "text",
            "use",
        ],
    ),
    DefaultAttribute("z", 0, elements=["fePointLight", "feSpotLight"]),
    DefaultAttribute("x1", 0, elements=["line"]),
    DefaultAttribute("y1", 0, elements=["line"]),
    DefaultAttribute("x2", 0, elements=["line"]),
    DefaultAttribute("y2", 0, elements=["line"]),
    DefaultAttribute("cx", 0, elements=["circle", "ellipse"]),
    DefaultAttribute("cy", 0, elements=["circle", "ellipse"]),
    # markers
    DefaultAttribute("markerUnits", "strokeWidth", elements=["marker"]),
    DefaultAttribute("refX", 0, elements=["marker"]),
    DefaultAttribute("refY", 0, elements=["marker"]),
    DefaultAttribute("markerHeight", 3, elements=["marker"]),
    DefaultAttribute("markerWidth", 3, elements=["marker"]),
    DefaultAttribute("orient", 0, elements=["marker"]),
    # text / textPath / tspan / tref
    DefaultAttribute("lengthAdjust", "spacing", elements=["text", "textPath", "tref", "tspan"]),
    DefaultAttribute("startOffset", 0, elements=["textPath"]),
    DefaultAttribute("method", "align", elements=["textPath"]),
    DefaultAttribute("spacing", "exact", elements=["textPath"]),
    # filters and masks
    DefaultAttribute("x", -10, 1, ["filter", "mask"]),  # Unit.PCT
    DefaultAttribute(
        "x",
        -0.1,
        0,  # Unit.NONE
        ["filter", "mask"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("y", -10, 1, ["filter", "mask"]),  # Unit.PCT
    DefaultAttribute(
        "y",
        -0.1,
        0,  # Unit.NONE
        ["filter", "mask"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("width", 120, 1, ["filter", "mask"]),  # Unit.PCT
    DefaultAttribute(
        "width",
        1.2,
        0,  # Unit.NONE
        ["filter", "mask"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("height", 120, 1, ["filter", "mask"]),  # Unit.PCT
    DefaultAttribute(
        "height",
        1.2,
        0,  # Unit.NONE
        ["filter", "mask"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    # gradients
    DefaultAttribute("x1", 0, elements=["linearGradient"]),
    DefaultAttribute("y1", 0, elements=["linearGradient"]),
    DefaultAttribute("y2", 0, elements=["linearGradient"]),
    DefaultAttribute("x2", 100, 1, elements=["linearGradient"]),  # Unit.PCT
    DefaultAttribute(
        "x2",
        1,
        0,  # Unit.NONE
        elements=["linearGradient"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    # remove fx/fy before cx/cy to catch the case where fx = cx = 50% or fy = cy = 50% respectively
    DefaultAttribute(
        "fx", elements=["radialGradient"], conditions=lambda node: node.getAttribute("fx") == node.getAttribute("cx")
    ),
    DefaultAttribute(
        "fy", elements=["radialGradient"], conditions=lambda node: node.getAttribute("fy") == node.getAttribute("cy")
    ),
    DefaultAttribute("r", 50, 1, elements=["radialGradient"]),  # Unit.PCT
    DefaultAttribute(
        "r",
        0.5,
        0,  # Unit.NONE
        elements=["radialGradient"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("cx", 50, 1, elements=["radialGradient"]),  # Unit.PCT
    DefaultAttribute(
        "cx",
        0.5,
        0,  # Unit.NONE
        elements=["radialGradient"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("cy", 50, 1, elements=["radialGradient"]),  # Unit.PCT
    DefaultAttribute(
        "cy",
        0.5,
        0,  # Unit.NONE
        elements=["radialGradient"],
        conditions=lambda node: node.getAttribute("gradientUnits") != "userSpaceOnUse",
    ),
    DefaultAttribute("spreadMethod", "pad", elements=["linearGradient", "radialGradient"]),
    # filter effects
    DefaultAttribute("amplitude", 1, elements=["feFuncA", "feFuncB", "feFuncG", "feFuncR"]),
    DefaultAttribute("azimuth", 0, elements=["feDistantLight"]),
    DefaultAttribute("baseFrequency", "0", elements=["feFuncA", "feFuncB", "feFuncG", "feFuncR"]),
    DefaultAttribute("bias", 1, elements=["feConvolveMatrix"]),
    DefaultAttribute("diffuseConstant", 1, elements=["feDiffuseLighting"]),
    DefaultAttribute("edgeMode", "duplicate", elements=["feConvolveMatrix"]),
    DefaultAttribute("elevation", 0, elements=["feDistantLight"]),
    DefaultAttribute("exponent", 1, elements=["feFuncA", "feFuncB", "feFuncG", "feFuncR"]),
    DefaultAttribute("intercept", 0, elements=["feFuncA", "feFuncB", "feFuncG", "feFuncR"]),
    DefaultAttribute("k1", 0, elements=["feComposite"]),
    DefaultAttribute("k2", 0, elements=["feComposite"]),
    DefaultAttribute("k3", 0, elements=["feComposite"]),
    DefaultAttribute("k4", 0, elements=["feComposite"]),
    DefaultAttribute("mode", "normal", elements=["feBlend"]),
    DefaultAttribute("numOctaves", 1, elements=["feTurbulence"]),
    DefaultAttribute("offset", 0, elements=["feFuncA", "feFuncB", "feFuncG", "feFuncR"]),
    DefaultAttribute("operator", "over", elements=["feComposite"]),
    DefaultAttribute("operator", "erode", elements=["feMorphology"]),
    DefaultAttribute("order", "3", elements=["feConvolveMatrix"]),
    DefaultAttribute("pointsAtX", 0, elements=["feSpotLight"]),
    DefaultAttribute("pointsAtY", 0, elements=["feSpotLight"]),
    DefaultAttribute("pointsAtZ", 0, elements=["feSpotLight"]),
    DefaultAttribute("preserveAlpha", "false", elements=["feConvolveMatrix"]),
    DefaultAttribute("radius", "0", elements=["feMorphology"]),
    DefaultAttribute("scale", 0, elements=["feDisplacementMap"]),
    DefaultAttribute("seed", 0, elements=["feTurbulence"]),
    DefaultAttribute("specularConstant", 1, elements=["feSpecularLighting"]),
    DefaultAttribute("specularExponent", 1, elements=["feSpecularLighting", "feSpotLight"]),
    DefaultAttribute("stdDeviation", "0", elements=["feGaussianBlur"]),
    DefaultAttribute("stitchTiles", "noStitch", elements=["feTurbulence"]),
    DefaultAttribute("surfaceScale", 1, elements=["feDiffuseLighting", "feSpecularLighting"]),
    DefaultAttribute("type", "matrix", elements=["feColorMatrix"]),
    DefaultAttribute("type", "turbulence", elements=["feTurbulence"]),
    DefaultAttribute("xChannelSelector", "A", elements=["feDisplacementMap"]),
    DefaultAttribute("yChannelSelector", "A", elements=["feDisplacementMap"]),
]

# Pre-split lookup structures for removeDefaultAttributeValues().
# - universal: attributes valid for ALL elements (currently empty — no universal defaults defined).
# - per_element: dict mapping element tag name (str) -> list[DefaultAttribute] for that element.
default_attributes_universal: list[DefaultAttribute] = []
default_attributes_per_element: dict[str, list[DefaultAttribute]] = defaultdict(list)
for default_attribute in default_attributes:
    if default_attribute.elements is None:  # pragma: no cover — currently no universal defaults exist
        default_attributes_universal.append(default_attribute)
    else:
        for element in default_attribute.elements:
            default_attributes_per_element[element].append(default_attribute)


# =============================================================================
# Canonical SVG Attribute Ordering
# =============================================================================

# Canonical ordering of SVG attributes for output.
# Known attributes appear first in this specific order; unknown attributes sort alphabetically.
# Used by _attribute_sort_key_function() and attributes_ordered_for_output().
# Note: Unit constants are replaced with their values here (Unit.PCT=1, Unit.NONE=0)
# to avoid circular imports from types.py.
#
# TODO: Maybe update with full list from https://www.w3.org/TR/SVG/attindex.html
KNOWN_ATTRS: tuple[list[str], ...] = (
    [
        "id",
        "xml:id",
        "class",
        "transform",
        "x",
        "y",
        "z",
        "width",
        "height",
        "x1",
        "x2",
        "y1",
        "y2",
        "dx",
        "dy",
        "rotate",
        "startOffset",
        "method",
        "spacing",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "fx",
        "fy",
        "d",
        "points",
    ]
    + sorted(svgAttributes)
    + [
        "style",
    ]
)

# Attribute name -> sort index for fast lookup during serialization.
# Default value (len(KNOWN_ATTRS)) pushes unknown attrs to the end, sorted alphabetically.
KNOWN_ATTRS_ORDER_BY_NAME: dict[str, int] = defaultdict(
    lambda: len(KNOWN_ATTRS), {name: order for order, name in enumerate(KNOWN_ATTRS)}
)
