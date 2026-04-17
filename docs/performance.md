# Performance

`svg_polish` is built around three knobs that trade between speed,
memory, and bit-for-bit reproducibility. This page explains what each
one does, when to flip it, and what the benchmarks say.

## Defaults: lossless and predictable

```python
from svg_polish import optimize
optimize(svg)
```

Out of the box you get:

- **Lossless** numerical handling (`decimal_engine="decimal"`) — every
  coordinate flows through `decimal.Decimal` and is rounded only by
  the configured precision.
- **`xml.dom.minidom`** XML backend — pure Python, zero deps beyond
  `defusedxml`, predictable behaviour across CPython versions.
- **5 significant digits** for normal coordinates, mirrored for
  control points (`digits=5`, `cdigits=-1`).

Use these defaults for build pipelines, CI, and any case where an SVG
must hash identically across machines.

## When to use the float engine

```python
from svg_polish import optimize, OptimizeOptions
optimize(svg, OptimizeOptions(decimal_engine="float"))
```

The float engine swaps `Decimal` for native `float` in the path and
transform parsers. Decimal arithmetic in CPython is implemented in C
but is still ~10× slower than float arithmetic; on dense path data the
parser dominates, so switching to floats yields a meaningful speedup.

**Use it when:**

- Throughput matters more than bit-for-bit reproducibility (e.g.
  serving optimised SVGs from a request handler with a tight budget).
- The output goes straight to a renderer — visual identity is the
  goal, not a hash check.
- You have profiled and confirmed that `clean_path` /
  `optimize_transforms` are the bottleneck.

**Skip it when:**

- Your CI pipeline diffs the SVG output to detect regressions —
  float rounding can change the last digit run-to-run.
- You produce content-addressed assets (cache keys derived from the
  output bytes).

## When to use lxml backend

`OptimizeOptions(xml_backend="lxml")` (or `"auto"`) selects the
optional `lxml` backend if installed:

```bash
pip install "svg-polish[fast]"
```

lxml is implemented in C and parses + serialises XML 3-5× faster than
`xml.dom.minidom` on inputs over ~50 KB. The optional install also
pulls `defusedxml[lxml]` so the secure-by-default posture is preserved.

The `"auto"` value picks lxml when (a) the package is importable and
(b) the input is larger than ~10 KB; small inputs incur lxml's
import-and-init overhead, which dominates the optimisation cost.

> **Note**: the lxml backend wiring is reserved for v1.x. Today the
> setting is accepted and validated but the optimiser still runs on
> `xml.dom.minidom`; the field is in place so v1.x callers don't have
> to rewrite their option construction when the backend ships.

## Tuning precision

`digits` and `cdigits` control how many significant digits the output
keeps. Lower numbers mean smaller files and more visual drift.

| Setting | Output character | When to use |
|---------|------------------|-------------|
| `digits=5` (default) | Indistinguishable from input at any zoom. | General use. |
| `digits=4` | Visible only at >2000% zoom. | Web icons, dashboards. |
| `digits=3` | Visible at >500% zoom; ~10-20% smaller. | Map tiles, preview thumbnails. |
| `digits=2` | Lossy. Acceptable only for thumbnails. | Aggressive size optimisation. |

`cdigits=-1` (the default) mirrors `digits`. Set it lower (e.g.
`cdigits=2` with `digits=4`) to tighten control-point precision —
control points tolerate more rounding than endpoint coordinates.

## Benchmarks

The repository ships a benchmark harness in `tests/benchmarks/`. It is
gated by the `benchmark` marker and excluded from default pytest runs.

```bash
poe bench                # save a baseline
poe bench-compare        # check current run against the saved baseline (5% tolerance)
```

Three fixture profiles are generated deterministically at session
start:

- **`dense-chart-50kb.svg`** — 50 KB chart-style SVG: many `<g>` with
  transforms, cubic-Bézier paths, a shared `<style>` block.
- **`dense-chart-100kb.svg`** — same shape, doubled.
- **`dense-paths-medium.svg`** — 60 KB of raw `<path>` elements with
  no grouping, mixed M/L/C/Q/A commands. Stresses the path parser.

Indicative runs on an Apple M-series CPU (CPython 3.12, no lxml):

| Fixture | Engine | Mean (ms) | Notes |
|---------|--------|-----------|-------|
| `dense-paths-medium.svg` | decimal | ~22 | minidom parse + Decimal arithmetic |
| `dense-paths-medium.svg` | float | ~24 | float arithmetic dominated by minidom |
| `dense-chart-100kb.svg` | decimal | ~45 | doubles linearly with size |
| `dense-chart-100kb.svg` | float | ~48 | float speedup masked by minidom |
| `dense-chart-100kb.svg` | float + `shorten_ids` | ~50 | adds an ID-rewrite pass |

The float-engine numbers are conservative because the bottleneck on
small/medium inputs is XML parsing, not arithmetic. The combined
*lxml backend + float engine* is where the headline 3-5× speedup
appears; the v1.x roadmap has lxml landing as a fully-wired backend
option.

## Profiling tips

`optimize_with_stats(svg)` returns wall-clock duration and per-pass
counters in a single call:

```python
from svg_polish import optimize_with_stats

result = optimize_with_stats(svg)
print(f"{result.duration_ms:.1f} ms — saved {result.saved_bytes} B")
print(result.stats)  # per-pass breakdown
```

For deeper profiling, run `python -m cProfile -o profile.out
your_script.py` and inspect with `snakeviz` or `pstats`. The two hot
spots usually are:

1. `xml.dom.minidom.parseString` — the largest single cost, addressed
   by the lxml backend.
2. `Decimal` arithmetic inside `clean_path` — addressed by the float
   engine on dense path data.

## Memory

The optimiser holds the entire DOM in memory plus working buffers that
are roughly the same size. For inputs over ~10 MB, the peak resident
size is typically 4-6× the input. `OptimizeOptions.max_input_bytes`
(default 100 MB) caps this; raise it deliberately if you process
unusually large SVGs in a long-lived process.
