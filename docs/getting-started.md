# Getting Started

## Requirements

- Python 3.10 or later

SVG Polish has **zero runtime dependencies**. It uses only the Python standard library.

## Installation

### From PyPI

```bash
pip install svg-polish
```

### With uv

```bash
uv add svg-polish
```

### From source

```bash
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish
uv sync
```

## Your First Optimization

### Command Line

```bash
# Optimize a file
svg-polish -i logo.svg -o logo-optimized.svg

# Pipe from stdin to stdout
cat logo.svg | svg-polish > logo-optimized.svg
```

### Python

```python
from svg_polish import optimize

svg_input = """
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="0" y="0" width="100" height="100"
        fill="#ff0000" stroke="#000000" stroke-width="1.000"/>
</svg>
"""

result = optimize(svg_input)
print(result)
```

Output:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
 <rect width="100" height="100" fill="red" stroke="#000" stroke-width="1"/>
</svg>
```

Notice what changed:
- `x="0" y="0"` removed (default values)
- `#ff0000` became `red` (shorter color name)
- `#000000` became `#000` (short hex)
- `1.000` became `1` (precision reduced)

### Optimize a File

```python
from svg_polish import optimize_file

result = optimize_file("logo.svg")
with open("logo-optimized.svg", "w") as f:
    f.write(result)
```

## Maximum Optimization

For the smallest possible output, combine all optimization flags:

```bash
svg-polish -i input.svg -o output.svg \
  --enable-viewboxing \
  --enable-id-stripping \
  --enable-comment-stripping \
  --shorten-ids \
  --indent=none \
  --no-line-breaks \
  --strip-xml-prolog
```

Or in Python:

```python
from svg_polish.optimizer import scourString, parse_args

options = parse_args([
    "--enable-viewboxing",
    "--enable-id-stripping",
    "--enable-comment-stripping",
    "--shorten-ids",
    "--indent=none",
    "--no-line-breaks",
    "--strip-xml-prolog",
])

result = scourString(svg_input, options)
```

## SVGZ (Compressed SVG)

Create gzip-compressed SVG files:

```bash
svg-polish -i input.svg -o output.svgz
```

The `.svgz` extension is automatically detected and the output is gzipped.

## Next Steps

- [Python API Reference](api.md) for the full API
- [CLI Reference](cli.md) for all command-line options
- [Optimization Guide](optimizations.md) for details on what gets optimized
