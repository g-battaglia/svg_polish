# Architecture

## Module Overview

```
src/svg_polish/
├── __init__.py          # Public API: optimize(), optimize_file()
├── optimizer.py         # Core optimization engine (~4600 lines)
├── stats.py             # ScourStats: optimization statistics
├── css.py               # Minimal CSS parser for <style> elements
├── svg_regex.py         # SVG path data parser (d attribute)
├── svg_transform.py     # SVG transform attribute parser
└── py.typed             # PEP 561 type marker
```

## Module Details

### `__init__.py` - Public API

Exposes three symbols:
- `optimize(svg_string, options=None) -> str` - Main entry point
- `optimize_file(filename, options=None) -> str` - File convenience wrapper
- `__version__` - Package version string

### `optimizer.py` - Core Engine

The heart of SVG Polish. Contains the full optimization pipeline.

**Key functions:**

| Function | Purpose |
|----------|---------|
| `scourString(in_string, options)` | Main optimization entry point |
| `scourXmlFile(filename, options)` | File-based optimization |
| `parse_args(args)` | CLI argument parsing |
| `start(options, infile, outfile)` | CLI entry point |
| `run()` | Script entry point |

**Optimization pipeline** (order of execution in `scourString`):

1. Parse SVG into DOM (`xml.dom.minidom`)
2. Remove editor data (Inkscape, Sodipodi, Adobe, Sketch)
3. Repair/optimize styles
4. Convert colors to short format
5. Remove unreferenced elements
6. Remove empty containers (`defs`, `g`, `metadata`)
7. Move common attributes to parent groups
8. Collapse groups
9. Merge sibling groups with common attributes
10. Create groups for common attributes (optional)
11. Move common attributes to parent groups (second pass)
12. Optimize path data
13. Reduce coordinate precision
14. Remove default attribute values
15. Optimize transforms
16. Shorten IDs (optional)
17. Create viewBox (optional)
18. Serialize to string

**Path optimization sub-pipeline** (within step 12):

1. Convert all commands to relative
2. Remove empty segments (zero-length moves, lines)
3. Remove no-op commands
4. Convert straight cubic curves to lines
5. First collapse: merge consecutive same-type commands
6. Convert `l` to `h`/`v` shorthand
7. Convert `c` to `s` shorthand
8. Collapse same-direction segments
9. Second collapse: merge consecutive same-type commands

### `stats.py` - Optimization Statistics

`ScourStats` class with `__slots__` for efficient storage. Tracks counts and byte savings for each optimization category.

### `css.py` - CSS Parser

Minimal CSS parser (`parseCssString`) that splits CSS into rules with selectors and property dictionaries. Used for processing `<style>` elements in SVGs.

### `svg_regex.py` - Path Data Parser

Regular expression-based parser for SVG path `d` attribute values. Handles all SVG path commands:

| Command | Parameters | Description |
|---------|------------|-------------|
| M/m | x,y | Move to |
| L/l | x,y | Line to |
| H/h | x | Horizontal line |
| V/v | y | Vertical line |
| C/c | x1,y1,x2,y2,x,y | Cubic bezier |
| S/s | x2,y2,x,y | Smooth cubic bezier |
| Q/q | x1,y1,x,y | Quadratic bezier |
| T/t | x,y | Smooth quadratic bezier |
| A/a | rx,ry,rot,large,sweep,x,y | Arc |
| Z/z | | Close path |

### `svg_transform.py` - Transform Parser

Parses SVG `transform` attribute values into structured data:

| Transform | Parameters |
|-----------|------------|
| `translate(tx, ty)` | Translation |
| `scale(sx, sy)` | Scale |
| `rotate(angle, cx, cy)` | Rotation |
| `skewX(angle)` | Horizontal skew |
| `skewY(angle)` | Vertical skew |
| `matrix(a,b,c,d,e,f)` | General affine |

## Data Flow

```
Input SVG (string or file)
        |
        v
  xml.dom.minidom.parseString()
        |
        v
  DOM Document
        |
        v
  Optimization passes (in-place DOM mutations)
        |
        v
  Custom serializer (serializeXML)
        |
        v
Output SVG string
```

The optimizer works directly on the minidom DOM tree, performing in-place mutations. The custom serializer at the end produces cleaner output than minidom's built-in `toxml()`.

## Design Decisions

**Why minidom?** The optimizer was originally written for Python 2.x when minidom was the standard choice. It works well for SVG files which are typically not very large.

**Why in-place mutation?** The optimization passes are applied sequentially, each modifying the DOM. This avoids the overhead of creating new trees at each step.

**Why a custom serializer?** minidom's `toxml()` produces verbose output with unnecessary whitespace. The custom serializer produces tighter output and handles SVG-specific formatting.

**Why `# pragma: no cover` on some lines?** A few code paths are unreachable in the current code flow:
- `default_attributes_universal` loop body: the list is always empty
- `remapNamespacePrefix` with non-empty prefix: always called with `""`
- ViewBox `ValueError` catch: values are scoured before this point
- `xmlns:` prefix in serialization: minidom always includes `xmlns` in `nodeName`
- `str.split()` returning empty list: impossible per Python specification

These are defensive code from the original Scour project and are preserved for safety.
