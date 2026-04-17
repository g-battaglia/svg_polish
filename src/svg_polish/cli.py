"""Command-line interface for ``svg-polish``.

This module owns the entire CLI surface — argument parser, file I/O,
exit-code handling, human-readable reporting — and exposes :func:`run`
as the ``svg-polish`` console entry point (registered in ``pyproject.toml``).

The split keeps optparse, argparse, and gzip/CLI-only imports out of the
``import svg_polish`` cold path. End users who only call :func:`optimize`
programmatically never load argparse, gzip, or this module.

The CLI still emits :class:`optparse.Values` for backward compatibility with
the legacy internal pipeline. The public, typed configuration is
:class:`~svg_polish.options.OptimizeOptions`; programmatic users should
prefer it.
"""

from __future__ import annotations

import optparse
import os
import sys
import time
from typing import IO, Any

from svg_polish.constants import APP, COPYRIGHT, VER
from svg_polish.optimizer import sanitize_options, scour_string
from svg_polish.options import DEFAULT_MAX_INPUT_BYTES
from svg_polish.stats import ScourStats

__all__ = [
    "HeaderedFormatter",
    "generate_report",
    "get_in_out",
    "maybe_gziped_file",
    "parse_args",
    "run",
    "start",
]


# =============================================================================
# Argument parser
# =============================================================================


class HeaderedFormatter(optparse.IndentedHelpFormatter):
    """Show application name, version, and copyright above usage information."""

    def format_usage(self, usage: str) -> str:
        """Prepend application name, version, and copyright to the usage string."""
        return f"{APP} {VER}\n{COPYRIGHT}\n{optparse.IndentedHelpFormatter.format_usage(self, usage)}"


# Module-level parser so callers can introspect defaults via
# ``_options_parser.get_default_values()`` or test against the registered
# option set without parsing argv.
_options_parser = optparse.OptionParser(
    usage="%prog [INPUT.SVG [OUTPUT.SVG]] [OPTIONS]",
    description=(
        "If the input/output files are not specified, stdin/stdout are used. "
        "If the input/output files are specified with a svgz extension, "
        "then compressed SVG is assumed."
    ),
    formatter=HeaderedFormatter(max_help_position=33),
    version=VER,
)

# legacy short alias retained from Scour for backwards compatibility
_options_parser.add_option("-p", action="store", type=int, dest="digits", help=optparse.SUPPRESS_HELP)

# general options
_options_parser.add_option(
    "-q", "--quiet", action="store_true", dest="quiet", default=False, help="suppress non-error output"
)
_options_parser.add_option(
    "-v", "--verbose", action="store_true", dest="verbose", default=False, help="verbose output (statistics, etc.)"
)
_options_parser.add_option(
    "-i", action="store", dest="infilename", metavar="INPUT.SVG", help="alternative way to specify input filename"
)
_options_parser.add_option(
    "-o", action="store", dest="outfilename", metavar="OUTPUT.SVG", help="alternative way to specify output filename"
)

_option_group_optimization = optparse.OptionGroup(_options_parser, "Optimization")
_option_group_optimization.add_option(
    "--set-precision",
    action="store",
    type=int,
    dest="digits",
    default=5,
    metavar="NUM",
    help="set number of significant digits (default: %default)",
)
_option_group_optimization.add_option(
    "--set-c-precision",
    action="store",
    type=int,
    dest="cdigits",
    default=-1,
    metavar="NUM",
    help="set number of significant digits for control points (default: same as '--set-precision')",
)
_option_group_optimization.add_option(
    "--decimal-engine",
    action="store",
    type="choice",
    choices=["decimal", "float"],
    dest="decimal_engine",
    default="decimal",
    metavar="ENGINE",
    help=(
        "numeric engine for path/transform parsing — 'decimal' (default, lossless) "
        "or 'float' (~3-5x faster on dense paths, opt-in, lossy)"
    ),
)
_option_group_optimization.add_option(
    "--disable-simplify-colors",
    action="store_false",
    dest="simple_colors",
    default=True,
    help="won't convert colors to #RRGGBB format",
)
_option_group_optimization.add_option(
    "--disable-style-to-xml",
    action="store_false",
    dest="style_to_xml",
    default=True,
    help="won't convert styles into XML attributes",
)
_option_group_optimization.add_option(
    "--disable-group-collapsing",
    action="store_false",
    dest="group_collapse",
    default=True,
    help="won't collapse <g> elements",
)
_option_group_optimization.add_option(
    "--create-groups",
    action="store_true",
    dest="group_create",
    default=False,
    help="create <g> elements for runs of elements with identical attributes",
)
_option_group_optimization.add_option(
    "--keep-editor-data",
    action="store_true",
    dest="keep_editor_data",
    default=False,
    help="won't remove Inkscape, Sodipodi, Adobe Illustrator or Sketch elements and attributes",
)
_option_group_optimization.add_option(
    "--keep-unreferenced-defs",
    action="store_true",
    dest="keep_defs",
    default=False,
    help="won't remove elements within the defs container that are unreferenced",
)
_option_group_optimization.add_option(
    "--renderer-workaround",
    action="store_true",
    dest="renderer_workaround",
    default=True,
    help="work around various renderer bugs (currently only librsvg) (default)",
)
_option_group_optimization.add_option(
    "--no-renderer-workaround",
    action="store_false",
    dest="renderer_workaround",
    default=True,
    help="do not work around various renderer bugs (currently only librsvg)",
)
_options_parser.add_option_group(_option_group_optimization)

_option_group_security = optparse.OptionGroup(_options_parser, "Security")
_option_group_security.add_option(
    "--allow-xml-entities",
    action="store_true",
    dest="allow_xml_entities",
    default=False,
    help="allow XML entities and DOCTYPE in input (UNSAFE for untrusted input — emits SecurityWarning)",
)
_option_group_security.add_option(
    "--max-input-bytes",
    action="store",
    type=int,
    dest="max_input_bytes",
    default=DEFAULT_MAX_INPUT_BYTES,
    metavar="BYTES",
    help="reject inputs larger than BYTES (default: %default; pass -1 to disable)",
)
_options_parser.add_option_group(_option_group_security)

_option_group_document = optparse.OptionGroup(_options_parser, "SVG document")
_option_group_document.add_option(
    "--strip-xml-prolog",
    action="store_true",
    dest="strip_xml_prolog",
    default=False,
    help="won't output the XML prolog (<?xml ?>)",
)
_option_group_document.add_option(
    "--remove-titles", action="store_true", dest="remove_titles", default=False, help="remove <title> elements"
)
_option_group_document.add_option(
    "--remove-descriptions",
    action="store_true",
    dest="remove_descriptions",
    default=False,
    help="remove <desc> elements",
)
_option_group_document.add_option(
    "--remove-metadata",
    action="store_true",
    dest="remove_metadata",
    default=False,
    help="remove <metadata> elements (which may contain license/author information etc.)",
)
_option_group_document.add_option(
    "--remove-descriptive-elements",
    action="store_true",
    dest="remove_descriptive_elements",
    default=False,
    help="remove <title>, <desc> and <metadata> elements",
)
_option_group_document.add_option(
    "--enable-comment-stripping",
    action="store_true",
    dest="strip_comments",
    default=False,
    help="remove all comments (<!-- -->)",
)
_option_group_document.add_option(
    "--disable-embed-rasters",
    action="store_false",
    dest="embed_rasters",
    default=True,
    help="won't embed rasters as base64-encoded data",
)
_option_group_document.add_option(
    "--enable-viewboxing",
    action="store_true",
    dest="enable_viewboxing",
    default=False,
    help="changes document width/height to 100%/100% and creates viewbox coordinates",
)
_options_parser.add_option_group(_option_group_document)

_option_group_formatting = optparse.OptionGroup(_options_parser, "Output formatting")
_option_group_formatting.add_option(
    "--indent",
    action="store",
    type="string",
    dest="indent_type",
    default="space",
    metavar="TYPE",
    help="indentation of the output: none, space, tab (default: %default)",
)
_option_group_formatting.add_option(
    "--nindent",
    action="store",
    type=int,
    dest="indent_depth",
    default=1,
    metavar="NUM",
    help="depth of the indentation, i.e. number of spaces/tabs: (default: %default)",
)
_option_group_formatting.add_option(
    "--no-line-breaks",
    action="store_false",
    dest="newlines",
    default=True,
    help='do not create line breaks in output(also disables indentation; might be overridden by xml:space="preserve")',
)
_option_group_formatting.add_option(
    "--strip-xml-space",
    action="store_true",
    dest="strip_xml_space_attribute",
    default=False,
    help='strip the xml:space="preserve" attribute from the root SVG element',
)
_option_group_formatting.add_option(
    "--attr-quote",
    action="store",
    type="string",
    dest="attr_quote",
    default="double",
    metavar="STYLE",
    help="preferred attribute delimiter: double, single (default: %default)",
)
_options_parser.add_option_group(_option_group_formatting)

_option_group_ids = optparse.OptionGroup(_options_parser, "ID attributes")
_option_group_ids.add_option(
    "--enable-id-stripping", action="store_true", dest="strip_ids", default=False, help="remove all unreferenced IDs"
)
_option_group_ids.add_option(
    "--shorten-ids",
    action="store_true",
    dest="shorten_ids",
    default=False,
    help="shorten all IDs to the least number of letters possible",
)
_option_group_ids.add_option(
    "--shorten-ids-prefix",
    action="store",
    type="string",
    dest="shorten_ids_prefix",
    default="",
    metavar="PREFIX",
    help="add custom prefix to shortened IDs",
)
_option_group_ids.add_option(
    "--protect-ids-noninkscape",
    action="store_true",
    dest="protect_ids_noninkscape",
    default=False,
    help="don't remove IDs not ending with a digit",
)
_option_group_ids.add_option(
    "--protect-ids-list",
    action="store",
    type="string",
    dest="protect_ids_list",
    metavar="LIST",
    help="don't remove IDs given in this comma-separated list",
)
_option_group_ids.add_option(
    "--protect-ids-prefix",
    action="store",
    type="string",
    dest="protect_ids_prefix",
    metavar="PREFIX",
    help="don't remove IDs starting with the given prefix",
)
_options_parser.add_option_group(_option_group_ids)

_option_group_compatibility = optparse.OptionGroup(_options_parser, "SVG compatibility checks")
_option_group_compatibility.add_option(
    "--error-on-flowtext",
    action="store_true",
    dest="error_on_flowtext",
    default=False,
    help="exit with error if the input SVG uses non-standard flowing text (only warn by default)",
)
_options_parser.add_option_group(_option_group_compatibility)


def parse_args(args: list[str] | None = None, ignore_additional_args: bool = False) -> optparse.Values:
    """Parse command-line arguments and return an options namespace."""
    options, rargs = _options_parser.parse_args(args)

    if rargs:
        if not options.infilename:
            options.infilename = rargs.pop(0)
        if not options.outfilename and rargs:
            options.outfilename = rargs.pop(0)
        if not ignore_additional_args and rargs:
            _options_parser.error(f"Additional arguments not handled: {rargs!r}, see --help")
    if options.digits < 1:
        _options_parser.error("Number of significant digits has to be larger than zero, see --help")
    if options.cdigits > options.digits:
        options.cdigits = -1
        print(
            "WARNING: The value for '--set-c-precision' should be lower than the value for '--set-precision'. "
            "Number of significant digits for control points reset to default value, see --help",
            file=sys.stderr,
        )
    if options.indent_type not in ["tab", "space", "none"]:
        _options_parser.error("Invalid value for --indent, see --help")
    if options.attr_quote not in ["double", "single"]:
        _options_parser.error("Invalid value for --attr-quote, see --help")
    if options.indent_depth < 0:
        _options_parser.error("Value for --nindent should be positive (or zero), see --help")
    if options.infilename and options.outfilename and options.infilename == options.outfilename:
        _options_parser.error("Input filename is the same as output filename")

    return options


# =============================================================================
# File I/O and reporting
# =============================================================================


def maybe_gziped_file(filename: str, mode: str = "r") -> IO[Any]:
    """Open *filename*, transparently decompressing ``.svgz``/``.gz`` files."""
    if os.path.splitext(filename)[1].lower() in (".svgz", ".gz"):
        import gzip

        return gzip.GzipFile(filename, mode)  # type: ignore[return-value]
    return open(filename, mode)


def get_in_out(options: optparse.Values) -> tuple[IO[Any], IO[Any]]:
    """Resolve input/output file handles from *options* (files or stdin/stdout)."""
    if options.infilename:
        infile = maybe_gziped_file(options.infilename, "rb")
    else:
        # open the binary buffer of stdin and let XML parser handle decoding
        try:
            infile = sys.stdin.buffer
        except AttributeError:  # pragma: no cover -- Python 3 always exposes .buffer
            infile = sys.stdin
        # the user probably does not want to manually enter SVG code into the terminal...
        if sys.stdin.isatty():
            _options_parser.error("No input file specified, see --help for detailed usage information")

    if options.outfilename:
        outfile = maybe_gziped_file(options.outfilename, "wb")
    else:
        # open the binary buffer of stdout as the output is already encoded
        try:
            outfile = sys.stdout.buffer
        except AttributeError:  # pragma: no cover -- Python 3 always exposes .buffer
            outfile = sys.stdout
        # redirect informational output to stderr when SVG is output to stdout
        options.stdout = sys.stderr

    return (infile, outfile)


def generate_report(stats: ScourStats) -> str:
    """Format optimization statistics into a human-readable report string.

    Each metric occupies one line, two-space indented, in the order returned
    by :class:`ScourStats`. Output uses :data:`os.linesep` so the report
    matches the host platform's newline convention when piped to a file.
    """
    return (
        "  Number of elements removed: "
        + str(stats.num_elements_removed)
        + os.linesep
        + "  Number of attributes removed: "
        + str(stats.num_attributes_removed)
        + os.linesep
        + "  Number of unreferenced IDs removed: "
        + str(stats.num_ids_removed)
        + os.linesep
        + "  Number of comments removed: "
        + str(stats.num_comments_removed)
        + os.linesep
        + "  Number of style properties fixed: "
        + str(stats.num_style_properties_fixed)
        + os.linesep
        + "  Number of raster images embedded: "
        + str(stats.num_rasters_embedded)
        + os.linesep
        + "  Number of path segments reduced/removed: "
        + str(stats.num_path_segments_removed)
        + os.linesep
        + "  Number of points removed from polygons: "
        + str(stats.num_points_removed_from_polygon)
        + os.linesep
        + "  Number of bytes saved in path data: "
        + str(stats.num_bytes_saved_in_path_data)
        + os.linesep
        + "  Number of bytes saved in colors: "
        + str(stats.num_bytes_saved_in_colors)
        + os.linesep
        + "  Number of bytes saved in comments: "
        + str(stats.num_bytes_saved_in_comments)
        + os.linesep
        + "  Number of bytes saved in IDs: "
        + str(stats.num_bytes_saved_in_ids)
        + os.linesep
        + "  Number of bytes saved in lengths: "
        + str(stats.num_bytes_saved_in_lengths)
        + os.linesep
        + "  Number of bytes saved in transformations: "
        + str(stats.num_bytes_saved_in_transforms)
    )


def start(options: optparse.Values, input_handle: IO[Any], output_handle: IO[Any]) -> None:
    """Run the optimizer: read from *input_handle*, optimize, write to *output_handle*."""
    options = sanitize_options(options)

    start_time = time.time()
    stats = ScourStats()

    # do the work
    in_string = input_handle.read()
    out_string = scour_string(in_string, options, stats=stats).encode("UTF-8")
    output_handle.write(out_string)

    # Close input and output files (but do not attempt to close stdin/stdout!)
    if not ((input_handle is sys.stdin) or (hasattr(sys.stdin, "buffer") and input_handle is sys.stdin.buffer)):
        input_handle.close()
    if not ((output_handle is sys.stdout) or (hasattr(sys.stdout, "buffer") and output_handle is sys.stdout.buffer)):
        output_handle.close()

    end_time = time.time()

    # run-time in ms
    duration = int(round((end_time - start_time) * 1000.0))

    oldsize = len(in_string)
    newsize = len(out_string)
    sizediff = (newsize / oldsize) * 100.0

    if not options.quiet:
        # ``noqa: E501`` — single-line f-string keeps the report message
        # readable. Splitting it would harm scannability without saving
        # cognitive load.
        message = (
            f'svg-polish processed file "{input_handle.name}" in '
            f"{duration} ms: {newsize}/{oldsize} bytes new/orig -> {sizediff:.1f}%"
        )
        print(message, file=options.ensure_value("stdout", sys.stdout))
        if options.verbose:
            print(generate_report(stats), file=options.ensure_value("stdout", sys.stdout))


def run() -> None:
    """CLI entry point: parse args, open files, run optimizer, write output."""
    options = parse_args()
    (input_handle, output_handle) = get_in_out(options)
    start(options, input_handle, output_handle)


if __name__ == "__main__":  # pragma: no cover
    run()
