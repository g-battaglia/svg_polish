# Optimization Guide

SVG Polish applies a comprehensive set of optimizations to reduce file size while preserving visual fidelity. All optimizations are **lossless by default**.

## Optimizations Applied by Default

### Editor Metadata Removal

SVG editors embed their own namespaces and elements that are not needed for rendering.

**Removed namespaces:**
- Inkscape (`inkscape:`, `sodipodi:`)
- Adobe Illustrator (`i:`, `x:`, `a:`)
- Sketch (`sketch:`)

**Before:**
```xml
<svg xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     inkscape:version="1.2"
     sodipodi:docname="logo.svg">
  <sodipodi:namedview id="base" pagecolor="#ffffff"/>
  <rect width="100" height="100"/>
</svg>
```

**After:**
```xml
<svg xmlns="http://www.w3.org/2000/svg">
  <rect width="100" height="100"/>
</svg>
```

### Color Optimization

Colors are converted to the shortest possible representation.

| Input | Output |
|-------|--------|
| `rgb(255,0,0)` | `red` |
| `rgb(0,0,0)` | `#000` |
| `#ff0000` | `red` |
| `#aabbcc` | `#abc` |
| `#000000` | `#000` |

This applies to both XML attributes and inline styles.

### Default Attribute Removal

Attributes that match their SVG default values are removed.

| Element | Attribute | Default Value |
|---------|-----------|---------------|
| `rect` | `x`, `y` | `0` |
| `rect` | `rx`, `ry` | `0` |
| `circle` | `cx`, `cy` | `0` |
| `line` | `x1`, `y1`, `x2`, `y2` | `0` |
| `stop` | `offset` | `0` |
| All | `clip-path` | `none` |
| All | `clip-rule` | `nonzero` |
| All | `fill-rule` | `nonzero` |
| All | `fill-opacity` | `1` |
| All | `stroke-opacity` | `1` |
| All | `stroke-miterlimit` | `4` |
| All | `stroke-dashoffset` | `0` |

### Path Data Optimization

SVG path data (`d` attribute) is heavily optimized:

1. **Absolute to relative coordinates** - relative commands are typically shorter
2. **Remove empty segments** - `l0,0` or `c0,0,0,0,0,0` are removed
3. **Straight curves to lines** - cubic beziers that form straight lines become `l` commands
4. **Line decomposition** - `l10,0` becomes `h10`, `l0,10` becomes `v10`
5. **Collapse same commands** - consecutive `h10 h20` becomes `h10 20`
6. **Same-direction collapse** - `h10 h20` (same sign) becomes `h30`
7. **Collapse to shorthand** - cubic beziers become `s` when control points mirror

**Before:**
```xml
<path d="M 10,10 L 20,10 L 20,20 L 10,20 Z"/>
```

**After:**
```xml
<path d="M10 10h10v10H10z"/>
```

### Precision Reduction

Numeric values are reduced to the configured precision (default: 5 significant digits).

| Before | After |
|--------|-------|
| `stroke-width="1.000000"` | `stroke-width="1"` |
| `opacity="0.500000"` | `opacity=".5"` |
| `font-size="12.000px"` | `font-size="12px"` |

### Group Collapsing

Redundant `<g>` elements are collapsed:

**Before:**
```xml
<g><g transform="translate(10,10)"><rect width="50" height="50"/></g></g>
```

**After:**
```xml
<g transform="translate(10,10)"><rect width="50" height="50"/></g>
```

### Duplicate Gradient Removal

Gradients with identical stops are deduplicated. References are updated automatically.

### Style Conversion

Inline `style` attributes are converted to XML presentation attributes:

**Before:**
```xml
<rect style="fill:red;stroke:blue"/>
```

**After:**
```xml
<rect fill="red" stroke="blue"/>
```

### Unreferenced Element Removal

Elements in `<defs>` that nothing references are removed (gradients, patterns, clip paths, etc.).

### Opacity Zero Cleanup

Elements with `opacity:0` have their fill and stroke properties stripped, since they are invisible.

### Transform Optimization

Transform attributes are simplified:

| Before | After |
|--------|-------|
| `translate(0)` | removed |
| `translate(10, 0)` | `translate(10)` |
| `scale(1)` | removed |
| `rotate(0)` | removed |
| `translate(10) translate(20)` | `translate(30)` |

### Raster Embedding

External raster images (`<image href="photo.png"/>`) are embedded as base64 data URIs by default.

---

## Optional Optimizations

These require explicit flags:

### ViewBox Creation (`--enable-viewboxing`)

Adds a `viewBox` attribute and removes `width`/`height`, making the SVG responsive.

### ID Stripping (`--enable-id-stripping`)

Removes all IDs that are not referenced by other elements.

### ID Shortening (`--shorten-ids`)

Replaces long IDs like `linearGradient1234` with minimal IDs like `a`, `b`, `c`.

### Comment Stripping (`--enable-comment-stripping`)

Removes all XML comments (`<!-- ... -->`).

### Group Creation (`--create-groups`)

Creates `<g>` elements to wrap runs of 3+ sibling elements that share common attributes, then promotes those attributes to the group.

---

## Precision Control

The `--set-precision` flag controls significant digits for coordinates:

| Precision | Example | Use Case |
|-----------|---------|----------|
| 3 | `12.3` | Icons, simple graphics |
| 5 (default) | `12.345` | General purpose |
| 8 | `12.345678` | High-detail illustrations |

Control points can have a different precision with `--set-c-precision`.
