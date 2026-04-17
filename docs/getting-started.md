# Getting Started

## Requirements

- Python 3.10 or later

`svg_polish` depends on `defusedxml` for secure-by-default XML parsing.
The optional `[fast]` extra adds `lxml` for ~3–5× faster parsing on
larger inputs.

## Installation

```bash
pip install svg-polish
```

With `uv`:

```bash
uv add svg-polish
```

For the optional fast XML backend:

```bash
pip install "svg-polish[fast]"
```

From source:

```bash
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish
uv sync
```

## Your first optimisation

### Command line

```bash
svg-polish -i logo.svg -o logo.min.svg
cat logo.svg | svg-polish > logo.min.svg
```

### Python

```python
from svg_polish import optimize

svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="0" y="0" width="100" height="100"
        fill="#ff0000" stroke="#000000" stroke-width="1.000"/>
</svg>
"""

print(optimize(svg))
```

Output:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
 <rect width="100" height="100" fill="red" stroke="#000" stroke-width="1"/>
</svg>
```

What changed:

- `x="0" y="0"` — removed (default values).
- `#ff0000` → `red` — shorter color name.
- `#000000` → `#000` — short hex form.
- `1.000` → `1` — precision reduced.

### Optimise a file

```python
from svg_polish import optimize_path

result = optimize_path("logo.svg")
```

`optimize_path` accepts `str` or `pathlib.Path`. The legacy
`optimize_file(filename)` is still exported for `str`-only callers but
new code should prefer `optimize_path`.

## Tuning with `OptimizeOptions`

Every public function accepts an `OptimizeOptions` dataclass. All
fields are optional; defaults are secure and lossless.

```python
from svg_polish import optimize, OptimizeOptions

opts = OptimizeOptions(
    digits=3,
    shorten_ids=True,
    enable_viewboxing=True,
    strip_comments=True,
)
optimized = optimize(svg, opts)
```

Equivalent CLI:

```bash
svg-polish -i input.svg -o output.svg \
  --set-precision=3 \
  --shorten-ids \
  --enable-viewboxing \
  --enable-comment-stripping
```

## Async usage

```python
import asyncio
from svg_polish import optimize_async

async def handler(svg: str) -> str:
    return await optimize_async(svg)

asyncio.run(handler(svg))
```

`optimize_async` offloads the synchronous optimiser to a worker
thread via `asyncio.to_thread`. The optimiser is reentrant and
thread-safe (per-call thread-local `Decimal` precision contexts), so
running it from an async web framework will not block the event loop.

## Stats

```python
from svg_polish import optimize_with_stats

result = optimize_with_stats(svg)
print(f"saved {result.saved_bytes} B "
      f"({result.saved_ratio:.1%}) "
      f"in {result.duration_ms:.1f} ms")
```

## SVGZ output

```bash
svg-polish -i input.svg -o output.svgz
```

The `.svgz` extension triggers gzip-compressed output automatically.

## Next steps

- [Python API Reference](api.md) — every public function in detail.
- [Configuration Guide](configuration.md) — `OptimizeOptions` field-by-field.
- [CLI Reference](cli.md) — every CLI flag.
- [Performance](performance.md) — when to flip `decimal_engine` /
  `xml_backend` / `digits`.
- [Security](security.md) — using `svg_polish` on untrusted input.
