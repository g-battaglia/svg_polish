# SVG Polish

**A fast, lossless SVG optimizer for Python.**

SVG Polish removes unnecessary data from SVG files — editor metadata, redundant attributes, verbose color formats, unoptimized paths — producing clean, lightweight vector graphics that render identically to the originals.

[![PyPI](https://img.shields.io/pypi/v/svg-polish.svg)](https://pypi.org/project/svg-polish/)
[![Python](https://img.shields.io/pypi/pyversions/svg-polish.svg)](https://pypi.org/project/svg-polish/)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/g-battaglia/svg_polish)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Why SVG Polish?

Most SVG editors (Inkscape, Illustrator, Figma, Sketch) embed metadata, default attributes, and editor-specific namespaces that bloat file sizes without affecting rendering. SVG Polish strips all of that away.

| Before | After |
|--------|-------|
| `style="fill:#ff0000;stroke:#000000"` | `fill="#f00"` |
| Editor namespaces (Inkscape, Adobe, Sodipodi) | Removed |
| Redundant XML declarations | Cleaned |
| Verbose path data | Optimized |

## Installation

Requires **Python 3.10+**.

```bash
pip install svg-polish
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add svg-polish
```

## Quick Start

### Command Line

Optimize a single file:

```bash
svg-polish -i input.svg -o output.svg
```

Read from stdin, write to stdout (great for piping):

```bash
cat input.svg | svg-polish > output.svg
```

Maximum optimization:

```bash
svg-polish -i input.svg -o output.svg \
  --enable-viewboxing \
  --enable-id-stripping \
  --enable-comment-stripping \
  --shorten-ids \
  --indent=none
```

Output as compressed SVGZ:

```bash
svg-polish -i input.svg -o output.svgz
```

### Python API

```python
from svg_polish import optimize, optimize_file

# Optimize a string
svg_input = open("input.svg").read()
svg_output = optimize(svg_input)

# Optimize a file directly
svg_output = optimize_file("input.svg")

# Write the result
with open("output.svg", "w") as f:
    f.write(svg_output)
```

### Advanced Usage

For fine-grained control, use the optimizer module directly:

```python
from svg_polish.optimizer import scourString, parse_args

# Configure specific options
options = parse_args([
    "--enable-viewboxing",
    "--enable-id-stripping",
    "--enable-comment-stripping",
    "--shorten-ids",
    "--set-precision=5",
    "--indent=none",
])

result = scourString(svg_input, options)
```

## What It Does

SVG Polish applies a comprehensive set of optimizations:

- **Removes editor metadata** — Inkscape, Sodipodi, Adobe Illustrator, Sketch namespaces and elements
- **Strips unnecessary attributes** — default values, empty attributes, redundant declarations
- **Optimizes colors** — converts `rgb(255,0,0)` to `#f00`, uses short color names where smaller
- **Optimizes path data** — removes unnecessary whitespace, converts absolute to relative coordinates, collapses segments
- **Removes unused definitions** — gradients, patterns, and filters that nothing references
- **Collapses groups** — removes pointless `<g>` wrappers
- **Shortens IDs** — optionally replaces long IDs with minimal ones
- **Removes comments** — optionally strips XML comments
- **Creates viewBox** — optionally adds `viewBox` and removes `width`/`height`
- **Embeds rasters** — converts referenced raster images to inline base64
- **Optimizes transforms** — simplifies transformation matrices
- **Reduces precision** — configurable decimal precision for coordinates

All optimizations are **lossless by default** — the output renders identically to the input.

## CLI Options

Run `svg-polish --help` for the full list. Key options:

| Option | Description |
|--------|-------------|
| `-i FILE` | Input SVG file (or use stdin) |
| `-o FILE` | Output SVG file (or use stdout) |
| `--set-precision=N` | Number of significant digits (default: 5) |
| `--enable-viewboxing` | Add viewBox, remove width/height |
| `--enable-id-stripping` | Remove unreferenced IDs |
| `--enable-comment-stripping` | Remove XML comments |
| `--shorten-ids` | Replace IDs with shorter versions |
| `--indent=TYPE` | Indentation: `space`, `tab`, or `none` |
| `--no-line-breaks` | Remove line breaks |
| `--strip-xml-prolog` | Remove XML declaration |
| `--disable-embed-rasters` | Keep raster images as external references |
| `--keep-editor-data` | Preserve editor-specific metadata |
| `--keep-unreferenced-defs` | Don't remove unused definitions |
| `-q` / `--quiet` | Suppress status output |
| `-v` / `--verbose` | Show detailed optimization statistics |

## Development

SVG Polish uses [uv](https://docs.astral.sh/uv/) for dependency management and [Poe the Poet](https://poethepoet.naber.dev/) for task running.

```bash
# Clone the repository
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish

# Install dependencies
uv sync

# Run tests
uv run poe test

# Run tests with coverage
uv run poe test-cov

# Lint and format
uv run poe lint
uv run poe format

# Type check
uv run poe typecheck

# Run all checks
uv run poe check
```

### Project Structure

```
svg_polish/
├── src/svg_polish/          # Source code
│   ├── __init__.py          # Public API (optimize, optimize_file)
│   ├── optimizer.py         # Core SVG optimization engine
│   ├── stats.py             # Optimization statistics
│   ├── css.py               # Minimal CSS parser
│   ├── svg_regex.py         # SVG path data parser
│   ├── svg_transform.py     # SVG transform parser
│   └── py.typed             # PEP 561 type marker
├── tests/                   # Test suite (469 tests, 100% coverage)
│   ├── test_optimizer.py    # Core optimizer tests
│   ├── test_public_api.py   # Public API tests
│   ├── test_css.py          # CSS parser tests
│   └── fixtures/            # SVG test fixtures
├── pyproject.toml           # Project configuration
├── LICENSE                  # Apache License 2.0
└── NOTICE                   # Attribution notices
```

## Origin and Attribution

SVG Polish is a fork of [Scour](https://github.com/scour-project/scour), an SVG optimizer originally created by **Jeff Schiller** and **Louis Simard** in 2010, later maintained by **Tobias Oberstein** and **Patrick Storz**.

This fork modernizes the project with:

- Python 3.10+ only (removed Python 2 compatibility and `six` dependency)
- Modern packaging with `pyproject.toml`, `uv`, and `hatchling`
- Type annotations and `py.typed` marker
- `pytest` test suite with coverage reporting
- Clean public API (`optimize()`, `optimize_file()`)
- Active maintenance

The original Scour project has been dormant since August 2021.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

The file `svg_regex.py` is derived from code by Enthought, Inc., licensed under the BSD 3-Clause License.

See [NOTICE](NOTICE) for full attribution.
