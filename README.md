# SVG Polish

**A fast, lossless, type-safe SVG optimizer for Python.**

`svg_polish` shrinks SVG files — strips editor metadata, collapses redundant attributes, dedups gradients, optimises path data and transforms — while guaranteeing that the output renders identically to the input. The library is fully typed (`py.typed`), thread-safe, secure-by-default against XML attacks, and ships with a single short API: `optimize()`.

[![PyPI](https://img.shields.io/pypi/v/svg-polish.svg)](https://pypi.org/project/svg-polish/)
[![Python](https://img.shields.io/pypi/pyversions/svg-polish.svg)](https://pypi.org/project/svg-polish/)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/g-battaglia/svg_polish)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Why SVG Polish

| Before | After |
|--------|-------|
| `style="fill:#ff0000;stroke:#000000"` | `fill="#f00"` |
| Inkscape / Sketch / Adobe namespaces | Removed |
| Verbose path commands | Collapsed and rounded |
| Duplicate gradients | Deduplicated |
| Hostile XXE / billion-laughs payload | Rejected before parsing |

## Install

Requires **Python 3.10+**.

```bash
pip install svg-polish
```

The default install is pure Python and depends only on `defusedxml`. For the optional fast XML backend (`lxml`, ~3-5× faster on large files):

```bash
pip install "svg-polish[fast]"
```

## Quick start

### Python

```python
from svg_polish import optimize

optimized = optimize('<svg xmlns="http://www.w3.org/2000/svg">…</svg>')
```

That's the whole pitch. Pass `OptimizeOptions` for tuning:

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

For metrics, use `optimize_with_stats`:

```python
from svg_polish import optimize_with_stats

result = optimize_with_stats(svg)
print(f"saved {result.saved_bytes} B ({result.saved_ratio:.1%}) in {result.duration_ms:.1f} ms")
```

For async web frameworks:

```python
from svg_polish import optimize_async

async def handler(svg: str) -> str:
    return await optimize_async(svg)
```

### Command line

```bash
svg-polish -i input.svg -o output.svg
cat input.svg | svg-polish > output.svg
svg-polish -i input.svg -o output.svgz       # gzip-compressed output
```

Aggressive settings:

```bash
svg-polish -i input.svg -o output.svg \
  --enable-viewboxing \
  --enable-id-stripping \
  --enable-comment-stripping \
  --shorten-ids \
  --indent=none
```

Run `svg-polish --help` for the full flag list.

## Public API

| Symbol | Purpose |
|--------|---------|
| `optimize(svg, options=None)` | Canonical entry point. Alias of `optimize_string`. |
| `optimize_string(svg, options=None)` | `str`/`bytes` in, `str` out. |
| `optimize_bytes(svg, options=None)` | `bytes` in, UTF-8 `bytes` out. |
| `optimize_path(path, options=None)` | Read from a filesystem path. |
| `optimize_async(svg, options=None)` | `await`-able wrapper via `asyncio.to_thread`. |
| `optimize_with_stats(svg, options=None)` | Returns an `OptimizeResult` with metrics. |
| `OptimizeOptions` | Frozen dataclass — the only configuration shape. |
| `OptimizeResult` | Optimised SVG + stats + duration. |
| `ScourStats` | Per-pass counters. |

Exceptions: `SvgPolishError` (base) → `SvgParseError`, `SvgPathSyntaxError`, `SvgTransformSyntaxError`, `SvgOptimizeError`, `SvgSecurityError`, `InvalidOptionError`. See [`docs/api.md`](docs/api.md) for the full reference.

## What it does

- Removes editor metadata (Inkscape, Sodipodi, Illustrator, Sketch).
- Strips default attribute values and empty attributes.
- Converts colors to the shortest equivalent form.
- Deduplicates `<linearGradient>` / `<radialGradient>` definitions.
- Collapses `<g>` wrappers and merges sibling groups.
- Optimises `<path>` `d` data (relative coords, h/v/s shortcuts, segment merging).
- Optimises `transform`, `patternTransform`, `gradientTransform`.
- Reduces numeric precision to a configurable digit count.
- Optionally shortens IDs, strips comments, converts to viewBox, embeds rasters.
- Custom serialiser produces tight, deterministic output.

All passes are **lossless** by default — see [`docs/performance.md`](docs/performance.md) for the opt-in `decimal_engine="float"` mode that trades reproducibility for ~3-5× faster numeric arithmetic.

## Security

Inputs are parsed through `defusedxml`, so XML external entity attacks, billion-laughs, and external DTD fetches are rejected before they touch the optimiser. Inputs over 100 MB are refused by default. See [`SECURITY.md`](SECURITY.md) for the threat model and [`docs/security.md`](docs/security.md) for usage patterns.

## Documentation

- [`docs/api.md`](docs/api.md) — Python API reference.
- [`docs/architecture.md`](docs/architecture.md) — module layout, layering, pipeline.
- [`docs/performance.md`](docs/performance.md) — tuning guide and benchmarks.
- [`docs/security.md`](docs/security.md) — usage patterns for untrusted input.
- [`docs/cli.md`](docs/cli.md) — command-line reference.
- [`docs/configuration.md`](docs/configuration.md) — `OptimizeOptions` field-by-field.

## Development

```bash
git clone https://github.com/g-battaglia/svg_polish.git
cd svg_polish
uv sync

uv run poe test          # full test suite (~660 tests)
uv run poe test-cov      # with coverage HTML report
uv run poe lint          # ruff lint
uv run poe format        # ruff format
uv run poe typecheck     # mypy strict
uv run poe check         # all of the above

uv run poe bench         # save a performance baseline
uv run poe bench-compare # compare current run against the baseline
```

## Origin

`svg_polish` is a fork of [Scour](https://github.com/scour-project/scour), originally created by **Jeff Schiller** and **Louis Simard** in 2010, later maintained by **Tobias Oberstein** and **Patrick Storz**. Upstream Scour has been dormant since August 2021. This v1.0 release is a ground-up modernisation:

- Python 3.10+ only; no `six`, no Python 2 compatibility shims.
- Single typed public surface (`OptimizeOptions`, `OptimizeResult`, `optimize_*`).
- Modular passes (one file per transformation) instead of a 4 700-line monolith.
- Thread-safe `Decimal` precision contexts.
- Secure-by-default XML parsing with `defusedxml`.
- 100% line coverage, `mypy --strict` clean, `ruff` clean.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

`svg_regex.py` is derived from code by Enthought, Inc. (BSD 3-Clause). Full attribution in [NOTICE](NOTICE).
