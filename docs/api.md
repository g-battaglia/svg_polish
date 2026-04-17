# Python API Reference

The canonical entry point is `svg_polish.optimize`. Configuration goes through the typed `OptimizeOptions` dataclass; results come back as plain `str`/`bytes`, or as a structured `OptimizeResult` when you ask for stats.

```python
from svg_polish import optimize, OptimizeOptions

optimized = optimize('<svg xmlns="http://www.w3.org/2000/svg">…</svg>')

# Tighter precision and ID shortening:
opts = OptimizeOptions(digits=3, shorten_ids=True)
optimized = optimize(svg, opts)
```

The optimization is **lossless by default** — the output renders identically to the input. The opt-in `decimal_engine="float"` mode trades the lossless guarantee for ~3-5× faster numeric arithmetic on dense paths.

---

## Primary API

All functions accept either an `OptimizeOptions` instance or `None` (uses defaults). Every public name is exported from the package root: `from svg_polish import optimize, optimize_path, …`.

### `optimize(svg, options=None) -> str`

Alias of `optimize_string`. The short, idiomatic name.

```python
from svg_polish import optimize

result = optimize('<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>')
```

### `optimize_string(svg, options=None) -> str`

Optimize an SVG string and return a `str`. Accepts `str` (Unicode) or `bytes` (any encoding declared in the XML prolog).

| Parameter | Type | Description |
|-----------|------|-------------|
| `svg` | `str \| bytes` | SVG content. Must be well-formed XML. |
| `options` | `OptimizeOptions \| None` | Configuration; `None` uses secure defaults. |

**Raises:**

- `SvgParseError` — input is not valid XML.
- `SvgSecurityError` — input violates a security policy (oversize, XML entities while disabled, etc.).

### `optimize_bytes(svg, options=None) -> bytes`

Bytes-in, bytes-out wrapper around `optimize_string`. Output is UTF-8 encoded.

### `optimize_path(path, options=None) -> str`

Read an SVG from a filesystem path and return the optimized `str`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str \| os.PathLike` | Filesystem path; `pathlib.Path` accepted. |
| `options` | `OptimizeOptions \| None` | Configuration. |

### `optimize_file(filename, options=None) -> str`

Legacy alias of `optimize_path` for `str` filenames only. Prefer `optimize_path` in new code.

### `async optimize_async(svg, options=None) -> str`

Offloads `optimize_string` to a worker thread via `asyncio.to_thread`. Safe to call from an async web framework — the thread-local `Decimal` contexts make the optimizer reentrant.

```python
import asyncio
from svg_polish import optimize_async

async def handler(svg: str) -> str:
    return await optimize_async(svg)
```

### `optimize_with_stats(svg, options=None) -> OptimizeResult`

Same as `optimize_string` but returns an `OptimizeResult` bundling savings metrics, byte sizes, and wall-clock duration.

```python
from svg_polish import optimize_with_stats

result = optimize_with_stats(svg)
print(f"saved {result.saved_bytes} bytes ({result.saved_ratio:.1%}) in {result.duration_ms:.1f} ms")
```

---

## Configuration

### `OptimizeOptions`

Frozen, slotted dataclass. Pass an instance to any `optimize*` function. Fields are documented inline (see `python -c "help(OptimizeOptions)"`); the most commonly tuned ones:

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `digits` | `int` | `5` | Significant-digit precision for normal coordinates. |
| `cdigits` | `int` | `-1` | Precision for control points (`-1` → mirror `digits`). |
| `decimal_engine` | `Literal["decimal","float"]` | `"decimal"` | `"float"` is faster (~3-5× on dense paths) but lossy. |
| `xml_backend` | `Literal["minidom"]` | `"minidom"` | Only `defusedxml.minidom` ships in v1.0; pluggable `lxml` backend planned for v1.x. |
| `allow_xml_entities` | `bool` | `False` | Enable only on **trusted** input; emits a `SecurityWarning`. |
| `max_input_bytes` | `int \| None` | `100 * 1024 * 1024` | Reject inputs larger than this. `None` disables. |
| `shorten_ids` | `bool` | `False` | Replace long IDs with short ones (`a`, `b`, …). |
| `enable_viewboxing` | `bool` | `False` | Convert `width`/`height` to `viewBox`. |
| `strip_comments` | `bool` | `False` | Drop XML comments. |
| `keep_editor_data` | `bool` | `False` | Preserve Inkscape/Sketch/Illustrator metadata. |

```python
from svg_polish import OptimizeOptions

opts = OptimizeOptions(
    digits=3,
    shorten_ids=True,
    enable_viewboxing=True,
    strip_comments=True,
)
```

The dataclass is frozen — derive variants with `dataclasses.replace`:

```python
from dataclasses import replace

tight = OptimizeOptions(digits=5)
extra_tight = replace(tight, digits=3, cdigits=2)
```

Invalid combinations raise `InvalidOptionError` at construction time.

### `OptimizeResult`

Returned by `optimize_with_stats`. Frozen dataclass.

| Attribute | Type | Description |
|-----------|------|-------------|
| `svg` | `str` | The optimized SVG. |
| `stats` | `ScourStats` | Per-pass counters (elements removed, bytes saved per category). |
| `input_bytes` | `int` | UTF-8 byte size of the input. |
| `output_bytes` | `int` | UTF-8 byte size of the output. |
| `duration_ms` | `float` | Wall-clock duration. |
| `saved_bytes` | `int` *(property)* | `input_bytes - output_bytes`. |
| `saved_ratio` | `float` *(property)* | `saved_bytes / input_bytes`, `0.0` for empty input. |

### `ScourStats`

Slotted dataclass with savings counters: `num_elements_removed`, `num_attributes_removed`, `num_comments_removed`, `num_style_properties_fixed`, `num_bytes_saved_in_*` (colors, ids, lengths, path_data, transforms), `num_path_segments_removed`, `num_points_removed_from_polygon`, `num_ids_kept`. Available on `OptimizeResult.stats` or by passing a manually-constructed instance through the lower-level pipeline.

---

## Exceptions

All public exceptions derive from `SvgPolishError`:

| Exception | When raised |
|-----------|-------------|
| `SvgPolishError` | Base class — catch this to handle any library error. |
| `SvgParseError` | Input cannot be parsed as well-formed XML. Includes `line`, `column`, `snippet` when available. |
| `SvgPathSyntaxError` | A `<path>` `d` attribute is malformed. |
| `SvgTransformSyntaxError` | A `transform=`/`patternTransform=`/`gradientTransform=` value is malformed. |
| `SvgOptimizeError` | Internal optimization failure (rare). |
| `InvalidOptionError` | An `OptimizeOptions` field is out of range. Also derives from `ValueError`. |
| `SvgSecurityError` | Input violates a security policy: oversize, custom entities while disabled, etc. |

```python
from svg_polish import optimize, SvgParseError, SvgSecurityError

try:
    optimize(untrusted_svg)
except SvgSecurityError as exc:
    log.warning("rejected suspicious SVG: %s", exc)
except SvgParseError as exc:
    log.info("malformed SVG at line %s col %s", exc.line, exc.column)
```

---

## Type Support

The package ships a `py.typed` marker (PEP 561). All public functions are fully typed; `mypy --strict` passes against user code that imports from `svg_polish`.

```python
from svg_polish import optimize, OptimizeOptions

result: str = optimize("<svg>…</svg>")
opts: OptimizeOptions = OptimizeOptions(digits=3)
```
