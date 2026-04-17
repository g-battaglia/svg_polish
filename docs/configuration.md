# Configuration Guide

Every public function accepts an `OptimizeOptions` instance — a frozen,
slotted dataclass that is the single configuration shape in v1.x.
Invalid values raise `InvalidOptionError` at construction time, so
misconfiguration shows up immediately rather than mid-optimisation.

```python
from svg_polish import optimize, OptimizeOptions

opts = OptimizeOptions(digits=3, shorten_ids=True)
optimized = optimize(svg, opts)
```

`OptimizeOptions()` (no arguments) gives the secure, lossless,
indented-output defaults documented in [`docs/api.md`](api.md).

## Building variants

Because `OptimizeOptions` is frozen, derive new presets with
`dataclasses.replace`:

```python
from dataclasses import replace
from svg_polish import OptimizeOptions

base = OptimizeOptions(digits=5)
web  = replace(base, digits=3, shorten_ids=True, strip_comments=True)
```

## Presets

### Default — safe, lossless, indented

```python
from svg_polish import OptimizeOptions

opts = OptimizeOptions()
```

Use for build-pipeline assets, snapshot tests, content-addressed
storage. Every coordinate flows through `decimal.Decimal`; output is
byte-exact across machines and CPython versions.

### Web — small, no whitespace

```python
opts = OptimizeOptions(
    enable_viewboxing=True,
    strip_ids=True,
    shorten_ids=True,
    strip_comments=True,
    remove_descriptive_elements=True,
    strip_xml_prolog=True,
    indent_type="none",
    newlines=False,
)
```

For HTML inlining and HTTP delivery.

### Editor-friendly — round-trip with design tools

```python
opts = OptimizeOptions(
    keep_editor_data=True,
    keep_defs=True,
    protect_ids_noninkscape=True,
)
```

Preserves Inkscape / Sketch / Illustrator metadata and IDs that look
hand-authored.

### High precision — technical illustrations

```python
opts = OptimizeOptions(digits=8, cdigits=8)
```

For CAD-style or scientific SVGs where coordinate accuracy matters
more than file size.

### Throughput — float engine, server-side

```python
opts = OptimizeOptions(decimal_engine="float")
```

Trades the lossless guarantee for ~3–5× faster numeric arithmetic on
dense paths. Use only when the output goes straight to a renderer
(visual identity is enough; bit-for-bit reproducibility is not). See
[`docs/performance.md`](performance.md) for the full trade-off
discussion.

## Field reference

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `digits` | `int` | `5` | Significant digits for normal coordinates. |
| `cdigits` | `int` | `-1` | Significant digits for control points; `-1` mirrors `digits`. |
| `decimal_engine` | `Literal["decimal","float"]` | `"decimal"` | `"float"` is faster but lossy. |
| `xml_backend` | `Literal["minidom"]` | `"minidom"` | Only `defusedxml.minidom` is wired in v1.0; the pluggable `lxml` backend is planned for v1.x. |
| `allow_xml_entities` | `bool` | `False` | Enable only on **trusted** input — emits `SecurityWarning`. |
| `max_input_bytes` | `int \| None` | `100 MB` | Reject inputs larger than this. `None` disables. |
| `simple_colors` | `bool` | `True` | Convert colors to the shortest equivalent form. |
| `style_to_xml` | `bool` | `True` | Convert inline `style="…"` to XML attributes. |
| `group_collapse` | `bool` | `True` | Collapse redundant `<g>` wrappers. |
| `group_create` | `bool` | `False` | Wrap runs of identical-attribute siblings in a new `<g>`. |
| `keep_editor_data` | `bool` | `False` | Preserve Inkscape / Sketch / Illustrator namespaces. |
| `keep_defs` | `bool` | `False` | Preserve unreferenced `<defs>` content. |
| `renderer_workaround` | `bool` | `True` | Apply librsvg compatibility workarounds. |
| `strip_xml_prolog` | `bool` | `False` | Drop `<?xml … ?>` declaration. |
| `remove_titles` | `bool` | `False` | Drop `<title>` elements. |
| `remove_descriptions` | `bool` | `False` | Drop `<desc>` elements. |
| `remove_metadata` | `bool` | `False` | Drop `<metadata>` elements. |
| `remove_descriptive_elements` | `bool` | `False` | Combined `title` + `desc` + `metadata` removal. |
| `strip_comments` | `bool` | `False` | Drop XML comments. |
| `embed_rasters` | `bool` | `True` | Inline raster `<image>` references as `data:` URIs. |
| `enable_viewboxing` | `bool` | `False` | Convert `width`/`height` to `viewBox`. |
| `indent_type` | `Literal["space","tab","none"]` | `"space"` | Output indentation. |
| `indent_depth` | `int` | `1` | Indentation width. |
| `newlines` | `bool` | `True` | Emit newlines between elements. |
| `strip_xml_space_attribute` | `bool` | `False` | Drop `xml:space="preserve"`. |
| `strip_ids` | `bool` | `False` | Remove all unreferenced IDs. |
| `shorten_ids` | `bool` | `False` | Replace IDs with `a`, `b`, … . |
| `shorten_ids_prefix` | `str` | `""` | Prefix for shortened IDs. |
| `protect_ids_noninkscape` | `bool` | `False` | Keep IDs that don't end in a digit. |
| `protect_ids_list` | `str \| None` | `None` | Comma-separated list of IDs to keep. |
| `protect_ids_prefix` | `str \| None` | `None` | Keep IDs starting with this prefix. |
| `error_on_flowtext` | `bool` | `False` | Treat non-standard `<flowText>` as an error. |
| `quiet` / `verbose` | `bool` | `False` | CLI output verbosity. |

The dataclass is fully typed: `from svg_polish import OptimizeOptions`
and `mypy --strict` will catch typos and out-of-range literals at
analysis time.

## ID protection

When using `strip_ids=True` or `shorten_ids=True`, narrow what gets
touched with the protection fields:

```python
opts = OptimizeOptions(
    shorten_ids=True,
    protect_ids_list="logo,icon-home,icon-search",
    protect_ids_prefix="js-",
)
```

`protect_ids_noninkscape=True` is a coarser heuristic — keep any ID
that doesn't end in a digit (i.e. probably hand-written rather than
editor-generated).

## CLI parity

Every field has a corresponding CLI flag — see [`docs/cli.md`](cli.md).
The CLI builds an `OptimizeOptions` from the parsed flags and hands it
to the same `optimize_string` entry point you'd call from Python.
