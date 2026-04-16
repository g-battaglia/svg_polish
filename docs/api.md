# Python API Reference

## Public API

SVG Polish provides a simple, high-level API through the `svg_polish` package.

### `svg_polish.optimize(svg_string, options=None)`

Optimize an SVG string and return the optimized result.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `svg_string` | `str \| bytes` | The SVG content to optimize. Accepts both `str` and `bytes` (UTF-8). |
| `options` | `object \| None` | Optional configuration. Use `parse_args()` from `svg_polish.optimizer` for advanced configuration. Defaults to `None` (use default settings). |

**Returns:** `str` - The optimized SVG.

**Example:**

```python
from svg_polish import optimize

# Basic usage
result = optimize('<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>')

# From bytes
result = optimize(b'<svg xmlns="http://www.w3.org/2000/svg">...</svg>')

# With options
from svg_polish.optimizer import parse_args
options = parse_args(["--enable-viewboxing", "--shorten-ids"])
result = optimize(svg_string, options)
```

### `svg_polish.optimize_file(filename, options=None)`

Optimize an SVG file and return the optimized result.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | `str` | Path to the SVG file to optimize. |
| `options` | `object \| None` | Optional configuration. |

**Returns:** `str` - The optimized SVG.

**Example:**

```python
from svg_polish import optimize_file

result = optimize_file("input.svg")
with open("output.svg", "w") as f:
    f.write(result)
```

### `svg_polish.__version__`

The package version as a string (e.g., `"1.0.0"`).

```python
from svg_polish import __version__
print(__version__)  # "1.0.0"
```

---

## Advanced API

For fine-grained control, use the optimizer module directly.

### `svg_polish.optimizer.scourString(in_string, options=None)`

The core optimization function. Takes an SVG string and returns the optimized version.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `in_string` | `str` | The SVG content to optimize. |
| `options` | `object \| None` | Options from `parse_args()`. If `None`, default options are used. |

**Returns:** `str` - The optimized SVG.

This is the same function called by `optimize()`, but without the `bytes` handling.

### `svg_polish.optimizer.scourXmlFile(filename, options=None)`

Optimize an SVG file and return the result as a DOM `Document` object.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | `str` | Path to the SVG file. |
| `options` | `object \| None` | Options from `parse_args()`. |

**Returns:** `xml.dom.minidom.Document` - The optimized SVG DOM.

### `svg_polish.optimizer.parse_args(args=None)`

Parse command-line style arguments into an options object.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `args` | `list[str] \| None` | List of command-line arguments (without the program name). If `None`, parses `sys.argv`. |

**Returns:** An `optparse.Values` object with all configuration options.

**Example:**

```python
from svg_polish.optimizer import parse_args

# Use specific options
options = parse_args([
    "--set-precision=3",
    "--enable-viewboxing",
    "--shorten-ids",
    "--indent=none",
])

# List all available options
options = parse_args(["--help"])  # Prints help and exits
```

### `svg_polish.optimizer.start(options, infile, outfile)`

Process an SVG file with the given options, writing the result to `outfile`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `options` | `object` | Options from `parse_args()`. |
| `infile` | `str` | Input file path. |
| `outfile` | `str` | Output file path. Use `.svgz` extension for gzip output. |

---

## Statistics

After optimization, statistics are available through the `ScourStats` class.

### `svg_polish.stats.ScourStats`

Holds optimization statistics. Key attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `num_elements_removed` | `int` | Number of elements removed |
| `num_attributes_removed` | `int` | Number of attributes removed |
| `num_comments_removed` | `int` | Number of comments removed |
| `num_style_properties_fixed` | `int` | Number of style properties cleaned up |
| `num_bytes_saved_in_colors` | `int` | Bytes saved from color optimization |
| `num_bytes_saved_in_ids` | `int` | Bytes saved from ID shortening |
| `num_bytes_saved_in_lengths` | `int` | Bytes saved from length precision |
| `num_bytes_saved_in_path_data` | `int` | Bytes saved from path optimization |
| `num_bytes_saved_in_transforms` | `int` | Bytes saved from transform optimization |
| `num_path_segments_removed` | `int` | Number of path segments removed |
| `num_points_removed_from_polygon` | `int` | Points removed from polygon/polyline |

---

## CSS Parser

### `svg_polish.css.parseCssString(css_text)`

Parse a CSS string into a list of rules. Used internally for processing `<style>` elements.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `css_text` | `str` | The CSS text to parse. |

**Returns:** `list[CSSRule]` - A list of CSS rules, each with `selector` and `properties` keys.

```python
from svg_polish.css import parseCssString

rules = parseCssString(".cls1 { fill: red; stroke: blue }")
# [{'selector': '.cls1', 'properties': {'fill': 'red', 'stroke': 'blue'}}]
```

---

## Type Support

SVG Polish ships with a `py.typed` marker (PEP 561), so type checkers like mypy will automatically pick up its type information.

```python
from svg_polish import optimize

result: str = optimize("<svg>...</svg>")  # Type-safe
```
