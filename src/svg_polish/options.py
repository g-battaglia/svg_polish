"""Public, typed configuration object for the optimizer.

:class:`OptimizeOptions` is the canonical way to pass settings to the public
API in svg_polish v1.0+. It replaces the legacy ``optparse.Values`` object
that flows through the internal pipeline (which remains as an implementation
detail of :mod:`svg_polish.cli` until the modularization sprints).

The dataclass is **frozen** to make options safe to share between threads and
to avoid surprise mutation during a multi-pass pipeline. Use
:func:`dataclasses.replace` to derive a modified copy:

    base = OptimizeOptions(digits=4)
    tighter = dataclasses.replace(base, digits=2, cdigits=2)

Validation happens in ``__post_init__`` and raises
:class:`~svg_polish.exceptions.InvalidOptionError` for any out-of-range value.
"""

from __future__ import annotations

import optparse
from dataclasses import dataclass, fields
from typing import Literal

from svg_polish.exceptions import InvalidOptionError

__all__ = ["DEFAULT_MAX_INPUT_BYTES", "OptimizeOptions"]


# Default upper bound for input size (100 MiB). Imported by both optimizer.py
# and cli.py so that the dataclass default and the secure-by-default ceiling
# enforced by the parser cannot drift apart.
DEFAULT_MAX_INPUT_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class OptimizeOptions:
    """Typed configuration for :func:`svg_polish.optimize` and related entry points.

    Every field has a sensible, secure-by-default value. The most security-
    sensitive defaults are :attr:`allow_xml_entities` (False) and
    :attr:`max_input_bytes` (100 MiB) — see :doc:`/security` for guidance.

    Attributes mirror the long-form CLI flags (without the ``--`` prefix and
    converted from kebab- to snake-case) so users can translate between
    programmatic and command-line use without surprises.
    """

    # ------------------------------------------------------------------ #
    # Numeric precision                                                  #
    # ------------------------------------------------------------------ #
    digits: int = 5
    """Significant digits retained for standard coordinates."""

    cdigits: int = -1
    """Significant digits retained for Bézier control points.

    The sentinel ``-1`` means "use the same value as :attr:`digits`". The
    sentinel is resolved during ``__post_init__`` so all downstream code sees
    a concrete positive integer.
    """

    decimal_engine: Literal["decimal", "float"] = "decimal"
    """Numeric engine used for coordinate scouring.

    ``"decimal"`` is lossless (default). ``"float"`` is faster but introduces
    rounding artefacts — opt-in only, gated behind an explicit choice so the
    lossless guarantee is never violated by accident. *Wired up in v1.0
    Sprint 7 (V4); accepted but not yet effective in earlier sprints.*
    """

    # ------------------------------------------------------------------ #
    # XML backend                                                        #
    # ------------------------------------------------------------------ #
    xml_backend: Literal["auto", "minidom", "lxml"] = "auto"
    """XML parser/serializer backend.

    ``"auto"`` picks ``lxml`` when available **and** the input is large
    enough to amortise its startup cost. ``"minidom"`` is the safe default
    backed by :mod:`defusedxml.minidom`. ``"lxml"`` requires installing the
    optional ``[fast]`` extra. *Wired up in v1.0 Sprint 6 (V3).*
    """

    allow_xml_entities: bool = False
    """When True, accept inputs containing custom DOCTYPE entity declarations.

    The default rejects such inputs to defend against billion-laughs and XXE
    attacks. Enable only for trusted producers; emits a
    :class:`SecurityWarning` on every parse.
    """

    max_input_bytes: int | None = DEFAULT_MAX_INPUT_BYTES
    """Upper bound on input size, measured before parsing.

    ``None`` disables the check. Inputs larger than the bound raise
    :class:`~svg_polish.exceptions.SvgSecurityError`. The default is
    deliberately generous (100 MiB); production endpoints should set a
    tighter bound (e.g. 2 MiB for user uploads).
    """

    # ------------------------------------------------------------------ #
    # Color and style                                                    #
    # ------------------------------------------------------------------ #
    simple_colors: bool = True
    """Convert color values to the shortest equivalent (``#RRGGBB``/named)."""

    style_to_xml: bool = True
    """Promote ``style="…"`` declarations to XML attributes when equivalent."""

    # ------------------------------------------------------------------ #
    # Group operations                                                   #
    # ------------------------------------------------------------------ #
    group_collapse: bool = True
    """Collapse redundant nested ``<g>`` elements."""

    group_create: bool = False
    """Wrap consecutive elements with identical attributes in a new ``<g>``."""

    # ------------------------------------------------------------------ #
    # Editor metadata                                                    #
    # ------------------------------------------------------------------ #
    keep_editor_data: bool = False
    """Preserve Inkscape, Sodipodi, Adobe Illustrator and Sketch metadata."""

    keep_defs: bool = False
    """Preserve unreferenced elements inside ``<defs>``."""

    renderer_workaround: bool = True
    """Apply librsvg workarounds for known rendering bugs."""

    # ------------------------------------------------------------------ #
    # Document structure                                                 #
    # ------------------------------------------------------------------ #
    strip_xml_prolog: bool = False
    """Omit the ``<?xml … ?>`` prolog from the output."""

    remove_titles: bool = False
    """Remove ``<title>`` elements."""

    remove_descriptions: bool = False
    """Remove ``<desc>`` elements."""

    remove_metadata: bool = False
    """Remove ``<metadata>`` elements (which may carry licence/author info)."""

    remove_descriptive_elements: bool = False
    """Remove ``<title>``, ``<desc>`` and ``<metadata>`` together."""

    strip_comments: bool = False
    """Remove all XML comments."""

    embed_rasters: bool = True
    """Embed externally-referenced raster images as base64 ``data:`` URIs."""

    enable_viewboxing: bool = False
    """Replace explicit width/height with 100%/100% and a viewBox."""

    # ------------------------------------------------------------------ #
    # Output formatting                                                  #
    # ------------------------------------------------------------------ #
    indent_type: Literal["space", "tab", "none"] = "space"
    """Indentation character (or none for a single-line output)."""

    indent_depth: int = 1
    """Number of indent characters per nesting level."""

    newlines: bool = True
    """Emit line breaks between elements."""

    strip_xml_space_attribute: bool = False
    """Drop ``xml:space="preserve"`` from the root element."""

    # ------------------------------------------------------------------ #
    # IDs                                                                #
    # ------------------------------------------------------------------ #
    strip_ids: bool = False
    """Remove unreferenced ``id`` attributes."""

    shorten_ids: bool = False
    """Shorten retained IDs to the smallest unique strings."""

    shorten_ids_prefix: str = ""
    """Prefix prepended to every shortened ID."""

    protect_ids_noninkscape: bool = False
    """Skip shortening for IDs whose final character is not a digit."""

    protect_ids_list: str | None = None
    """Comma-separated allow-list of IDs to leave untouched."""

    protect_ids_prefix: str | None = None
    """Comma-separated list of ID prefixes to leave untouched."""

    # ------------------------------------------------------------------ #
    # Compatibility / diagnostics                                        #
    # ------------------------------------------------------------------ #
    error_on_flowtext: bool = False
    """Raise instead of warning when ``<flowText>`` elements are detected."""

    quiet: bool = False
    """Suppress non-error output from the CLI."""

    verbose: bool = False
    """Emit detailed statistics from the CLI."""

    # ------------------------------------------------------------------ #
    # Validation                                                         #
    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        if self.digits < 1:
            raise InvalidOptionError(f"digits must be >= 1 (got {self.digits!r})")
        if self.cdigits == -1:
            # Frozen dataclasses block normal assignment; ``object.__setattr__``
            # is the documented escape hatch for this exact use case
            # (resolving sentinels in ``__post_init__``).
            object.__setattr__(self, "cdigits", self.digits)
        if self.cdigits < 1:
            raise InvalidOptionError(f"cdigits must be >= 1 (got {self.cdigits!r})")
        if self.indent_depth < 0:
            raise InvalidOptionError(f"indent_depth must be >= 0 (got {self.indent_depth!r})")
        if self.indent_type not in ("space", "tab", "none"):
            raise InvalidOptionError(f"invalid indent_type: {self.indent_type!r}")
        if self.decimal_engine not in ("decimal", "float"):
            raise InvalidOptionError(f"invalid decimal_engine: {self.decimal_engine!r}")
        if self.xml_backend not in ("auto", "minidom", "lxml"):
            raise InvalidOptionError(f"invalid xml_backend: {self.xml_backend!r}")
        if self.max_input_bytes is not None and self.max_input_bytes < 1024:
            raise InvalidOptionError(f"max_input_bytes must be >= 1024 or None (got {self.max_input_bytes!r})")

    # ------------------------------------------------------------------ #
    # Internal bridge (temporary — removed in Sprint 4-5 modularization) #
    # ------------------------------------------------------------------ #
    def _to_optparse_values(self) -> optparse.Values:
        """Convert this dataclass into the legacy ``optparse.Values`` shape.

        The internal scouring pipeline still expects the Scour-era
        ``optparse.Values`` object. This bridge lets the public API accept
        :class:`OptimizeOptions` while we incrementally migrate the internal
        functions in subsequent sprints.

        Removed once all internal modules accept ``OptimizeOptions`` natively
        (Sprint 4-5 modularization).
        """
        values = optparse.Values()
        for field in fields(self):
            setattr(values, field.name, getattr(self, field.name))
        # The legacy parser also exposes these CLI-only fields; downstream code
        # may inspect them (e.g. ``options.infilename``), so populate with
        # ``None`` defaults to avoid AttributeError surprises.
        values.infilename = None
        values.outfilename = None
        return values
