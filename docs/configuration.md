# Configuration Guide

SVG Polish can be configured through CLI flags or by passing an options object to the Python API.

## Creating Options in Python

```python
from svg_polish.optimizer import parse_args, scourString

# Parse CLI-style arguments into an options object
options = parse_args([
    "--set-precision=3",
    "--enable-viewboxing",
    "--shorten-ids",
])

result = scourString(svg_input, options)
```

The `parse_args()` function accepts the same flags as the CLI.

## Configuration Presets

### Minimal (default behavior)

Safe optimizations only. No data is removed that could affect rendering or tooling:

```python
options = parse_args([])
```

### Web-optimized

Best for web delivery. Strips all non-essential data:

```python
options = parse_args([
    "--enable-viewboxing",
    "--enable-id-stripping",
    "--enable-comment-stripping",
    "--shorten-ids",
    "--remove-descriptive-elements",
    "--strip-xml-prolog",
    "--indent=none",
    "--no-line-breaks",
])
```

### Design-tool friendly

Preserves editor metadata and IDs for round-tripping with design tools:

```python
options = parse_args([
    "--keep-editor-data",
    "--keep-unreferenced-defs",
    "--protect-ids-noninkscape",
])
```

### High precision

For technical illustrations where coordinate accuracy matters:

```python
options = parse_args([
    "--set-precision=8",
    "--set-c-precision=8",
])
```

### Minimal impact

Only apply the safest, most impactful optimizations:

```python
options = parse_args([
    "--disable-group-collapsing",
    "--disable-style-to-xml",
    "--keep-unreferenced-defs",
])
```

## Option Reference

### Controlling What Gets Removed

| What | Keep it | Remove it |
|------|---------|-----------|
| Editor data | `--keep-editor-data` | (default) |
| Unreferenced defs | `--keep-unreferenced-defs` | (default) |
| Comments | (default) | `--enable-comment-stripping` |
| `<title>` elements | (default) | `--remove-titles` |
| `<desc>` elements | (default) | `--remove-descriptions` |
| `<metadata>` elements | (default) | `--remove-metadata` |
| All descriptive elements | (default) | `--remove-descriptive-elements` |
| Unreferenced IDs | (default) | `--enable-id-stripping` |

### Controlling Optimizations

| Optimization | Enable | Disable |
|--------------|--------|---------|
| Color simplification | (default) | `--disable-simplify-colors` |
| Style to XML conversion | (default) | `--disable-style-to-xml` |
| Group collapsing | (default) | `--disable-group-collapsing` |
| Raster embedding | (default) | `--disable-embed-rasters` |
| Renderer workarounds | (default) | `--no-renderer-workaround` |
| ViewBox creation | `--enable-viewboxing` | (default) |
| Group creation | `--create-groups` | (default) |
| ID shortening | `--shorten-ids` | (default) |

### ID Protection

When using `--enable-id-stripping` or `--shorten-ids`, you can protect specific IDs:

```bash
# Protect specific IDs
svg-polish -i input.svg -o output.svg --shorten-ids \
  --protect-ids-list=logo,icon-home,icon-search

# Protect IDs with a prefix
svg-polish -i input.svg -o output.svg --shorten-ids \
  --protect-ids-prefix=js-

# Protect IDs not ending with digits (likely hand-written)
svg-polish -i input.svg -o output.svg --shorten-ids \
  --protect-ids-noninkscape
```

## Using with the Public API

The simplest API uses default options:

```python
from svg_polish import optimize

# Default optimization
result = optimize(svg_string)
```

For custom options, pass them through:

```python
from svg_polish import optimize
from svg_polish.optimizer import parse_args

options = parse_args(["--shorten-ids", "--enable-viewboxing"])
result = optimize(svg_string, options)
```
