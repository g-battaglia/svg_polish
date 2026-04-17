# Optimization Guide

`svg_polish` applies a comprehensive set of transformations to reduce
file size while preserving visual fidelity. Every optimisation is
**lossless by default** — the output renders identically to the input
when `decimal_engine="decimal"` (the default).

The flags below have CLI form (e.g. `--enable-viewboxing`) and an
equivalent `OptimizeOptions` field (e.g.
`OptimizeOptions(enable_viewboxing=True)`). See
[`docs/configuration.md`](configuration.md) for the full mapping.

## Applied by default

### Editor metadata removal

SVG editors embed their own namespaces and elements that aren't needed
for rendering.

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

Disable with `keep_editor_data=True` / `--keep-editor-data`.

### Color optimization

Colors are converted to the shortest possible representation.

| Input | Output |
|-------|--------|
| `rgb(255,0,0)` | `red` |
| `rgb(0,0,0)` | `#000` |
| `#ff0000` | `red` |
| `#aabbcc` | `#abc` |
| `#000000` | `#000` |

Applies to both XML attributes and inline styles. Disable with
`simple_colors=False` / `--disable-simplify-colors`.

### Default attribute removal

Attributes that match SVG defaults are removed.

| Element | Attribute | Default |
|---------|-----------|---------|
| `rect` | `x`, `y`, `rx`, `ry` | `0` |
| `circle` | `cx`, `cy` | `0` |
| `line` | `x1`, `y1`, `x2`, `y2` | `0` |
| `stop` | `offset` | `0` |
| All | `clip-path` | `none` |
| All | `clip-rule`, `fill-rule` | `nonzero` |
| All | `fill-opacity`, `stroke-opacity` | `1` |
| All | `stroke-miterlimit` | `4` |
| All | `stroke-dashoffset` | `0` |

### Path data optimization

The `d` attribute is rewritten through an 8-phase pipeline (see
[`docs/architecture.md`](architecture.md) for the full list):

1. Absolute → relative coordinates.
2. Remove zero-length segments.
3. Convert straight cubic curves to lines.
4. Convert `l dx 0` to `h dx`, `l 0 dy` to `v dy`.
5. Collapse runs of the same command type.
6. Same-direction collapse (`h10 h20` → `h30`).
7. Convert `c` → `s` when the first control point mirrors.
8. Final consolidation pass.

**Before:**

```xml
<path d="M 10,10 L 20,10 L 20,20 L 10,20 Z"/>
```

**After:**

```xml
<path d="M10 10h10v10H10z"/>
```

The output is only kept if it is strictly shorter than the input — a
safety net against pathological cases.

### Precision reduction

Numeric values are reduced to the configured precision (default: 5
significant digits).

| Before | After |
|--------|-------|
| `stroke-width="1.000000"` | `stroke-width="1"` |
| `opacity="0.500000"` | `opacity=".5"` |
| `font-size="12.000px"` | `font-size="12px"` |

Tune with `digits` / `--set-precision` and `cdigits` /
`--set-c-precision`. See [`docs/performance.md`](performance.md) for
the precision-vs-size table.

### Group collapsing

Redundant `<g>` wrappers are collapsed:

**Before:**

```xml
<g><g transform="translate(10,10)"><rect width="50" height="50"/></g></g>
```

**After:**

```xml
<g transform="translate(10,10)"><rect width="50" height="50"/></g>
```

Disable with `group_collapse=False` / `--disable-group-collapsing`.

### Duplicate gradient removal

`<linearGradient>` and `<radialGradient>` definitions with identical
stops are deduplicated. References (`url(#…)`) are rewritten
automatically.

### Style conversion

Inline `style` attributes become XML presentation attributes:

**Before:**

```xml
<rect style="fill:red;stroke:blue"/>
```

**After:**

```xml
<rect fill="red" stroke="blue"/>
```

Disable with `style_to_xml=False` / `--disable-style-to-xml`.

### Unreferenced element removal

Elements in `<defs>` that nothing references are removed (gradients,
patterns, clip paths, etc.). Disable with `keep_defs=True` /
`--keep-unreferenced-defs`.

### Opacity-zero cleanup

Elements with `opacity:0` have their `fill` and `stroke` properties
stripped, since they are invisible.

### Transform optimization

Transform attributes are simplified:

| Before | After |
|--------|-------|
| `translate(0)` | removed |
| `translate(10, 0)` | `translate(10)` |
| `scale(1)` | removed |
| `rotate(0)` | removed |
| `translate(10) translate(20)` | `translate(30)` |

Applies to `transform`, `patternTransform`, and `gradientTransform`.

### Raster embedding

External raster images (`<image href="photo.png"/>`) are inlined as
`data:` URIs by default. Disable with `embed_rasters=False` /
`--disable-embed-rasters`. The `urllib` import is lazy — disabled
embedding pays no cost.

## Opt-in optimizations

These require explicit enabling via `OptimizeOptions` or CLI flags.

### ViewBox creation (`enable_viewboxing` / `--enable-viewboxing`)

Adds a `viewBox` attribute and removes `width`/`height`, making the
SVG responsive.

### ID stripping (`strip_ids` / `--enable-id-stripping`)

Removes all IDs that are not referenced by other elements.

### ID shortening (`shorten_ids` / `--shorten-ids`)

Replaces long IDs (`linearGradient1234`) with minimal IDs (`a`, `b`,
`c`). Combine with `shorten_ids_prefix` to namespace the output.

### Comment stripping (`strip_comments` / `--enable-comment-stripping`)

Removes all XML comments.

### Group creation (`group_create` / `--create-groups`)

Creates `<g>` wrappers around runs of three or more sibling elements
that share common attributes, then promotes those attributes to the
new group.

## Precision control

| `digits` | Output character | Use case |
|---|---|---|
| `5` (default) | Indistinguishable at any zoom. | General use. |
| `4` | Visible only at >2000 % zoom. | Web icons, dashboards. |
| `3` | Visible at >500 % zoom; ~10–20 % smaller. | Map tiles, thumbnails. |
| `2` | Lossy. | Aggressive size optimisation. |

`cdigits` (control points) defaults to mirror `digits`. Set it lower
to tighten control-point precision while keeping endpoint coordinates
high-fidelity.

## Engine choice

`OptimizeOptions(decimal_engine="float")` swaps the parsers from
`Decimal` to native `float` for ~3–5× faster numeric arithmetic on
dense paths. The trade-off — no longer bit-for-bit reproducible — is
documented in [`docs/performance.md`](performance.md).
