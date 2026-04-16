# Changelog

All notable changes to this project will be documented in this file.

## 1.0.0 (2026-04-16)

Initial release of SVG Polish, a fork of [Scour](https://github.com/scour-project/scour) v0.38.2.

### What's New

- **Modern Python**: Requires Python 3.10+, removed Python 2 compatibility and `six` dependency
- **Clean public API**: `optimize()` and `optimize_file()` functions for easy integration
- **Modern packaging**: `pyproject.toml` with `hatchling`, `uv` for dependency management, `poethepoet` for tasks
- **Type annotations**: `py.typed` marker and type hints on public API
- **pytest test suite**: 283 tests with 94% code coverage
- **CLI command**: `svg-polish` (replaces `scour`)

### Inherited from Scour 0.38.2

All optimization features from the original Scour project:

- Remove editor metadata (Inkscape, Sodipodi, Adobe Illustrator, Sketch)
- Strip unnecessary attributes and default values
- Optimize colors, path data, and transforms
- Remove unused definitions, collapse groups
- Shorten IDs, remove comments, create viewBox
- Embed raster images as base64
- Reduce numeric precision
- SVGZ (gzip) output support
