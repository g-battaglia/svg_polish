# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] — Initial release

First public release of `svg_polish` — a fast, lossless, type-safe SVG
optimizer for Python.

### Public API

- `optimize(svg, options=None)` — canonical entry point; alias of
  `optimize_string`.
- `optimize_string`, `optimize_bytes`, `optimize_path`, `optimize_file`
  — string/bytes/filesystem variants.
- `optimize_async` — `await`-able wrapper for async web frameworks.
- `optimize_with_stats` — returns `OptimizeResult` with savings,
  per-pass counters, and wall-clock duration.
- `OptimizeOptions` — frozen, slotted dataclass; the only configuration
  shape accepted by every public function. Validates field
  combinations at construction; invalid values raise
  `InvalidOptionError`.
- `OptimizeResult`, `ScourStats` — typed result containers with
  `saved_bytes` / `saved_ratio` properties.
- Exception hierarchy rooted at `SvgPolishError`:
  `SvgParseError`, `SvgPathSyntaxError`, `SvgTransformSyntaxError`,
  `SvgOptimizeError`, `SvgSecurityError`, `InvalidOptionError`.

### Security

- `defusedxml` is a hard runtime dependency. Inputs are parsed with
  `defusedxml.minidom` by default; XXE, billion-laughs, and external
  DTD fetches are rejected before reaching the optimiser.
- `OptimizeOptions.allow_xml_entities=False` (default) refuses inputs
  that declare XML entities. Set `True` only for trusted input — emits
  a `SecurityWarning`.
- `OptimizeOptions.max_input_bytes=100 MB` (default) bounds memory
  use against oversize-input attacks. `None` disables.
- See `SECURITY.md` for the full threat model and `docs/security.md`
  for usage patterns on untrusted input.

### Performance

- `OptimizeOptions.decimal_engine="float"` opt-in mode runs the path
  and transform parsers on native `float` for ~3–5× faster numeric
  arithmetic on dense paths. Default `"decimal"` keeps the lossless,
  bit-for-bit-reproducible behaviour.
- `OptimizeOptions.xml_backend="minidom"` is the only backend in v1.0
  (typed as a single-value `Literal`; passing `"lxml"` or `"auto"`
  raises `InvalidOptionError` rather than silently no-op'ing). A
  pluggable `lxml` backend behind the optional `svg-polish[fast]`
  extra is planned for a v1.x release.
- Per-call thread-local `Decimal` precision context
  (`precision_scope`) — `optimize_*` is reentrant and thread-safe.
  Different `digits` settings on concurrent threads produce
  byte-exact, deterministic output.
- `lru_cache` on the URL-reference regex builder; bounded growth
  under heavy ID churn.
- Benchmark harness in `tests/benchmarks/` with three deterministic
  fixtures (dense charts at 50 KB / 100 KB, dense raw paths). Run
  `poe bench` to save a baseline and `poe bench-compare` to check
  regressions against a 5 % tolerance.

### Architecture

- Modularised: `optimizer.py` is now a ~600-line orchestrator. Each
  optimisation pass lives in its own module (`passes/path.py`,
  `passes/transform.py`, etc.). Cross-cutting helpers (`dom.py`,
  `style.py`, `colors.py`, `ids.py`, `groups.py`, `gradients.py`,
  `namespaces.py`, `serialize.py`) are layered with strict
  bottom-up imports — circular imports are a CI failure.
- CLI extracted into `svg_polish.cli`. The console script
  (`svg-polish`) is the only entry point that touches `optparse` /
  `argparse`; the library has no CLI dependency on the import path.
- `urllib` import is lazy inside `passes/rasters.py`, so the common
  `import svg_polish` cost stays minimal.

### Quality

- Python 3.10+ only. Removed `six`, `from __future__` shims, and all
  Python 2 compatibility code.
- 660+ tests across `tests/`, including dedicated suites for security
  (`test_security.py`), concurrency (`test_concurrency.py`), exception
  hierarchy (`test_exceptions.py`), options validation
  (`test_options.py`), and float-engine isolation
  (`test_float_engine.py`).
- 100 % line coverage. `mypy --strict` clean. `ruff check` and
  `ruff format --check` clean.
- PEP 561 typed (`py.typed` marker). All public functions, dataclasses,
  and exceptions are fully annotated.

### Origin

`svg_polish` is a ground-up modernisation of
[Scour](https://github.com/scour-project/scour) v0.38.2, originally
created by Jeff Schiller and Louis Simard in 2010 and later maintained
by Tobias Oberstein and Patrick Storz. Upstream Scour has been dormant
since August 2021. This release rebuilds the public surface, hardens
the security posture, modularises the monolithic `scour.py`, and
introduces a typed configuration / result API.

Output is **byte-exact identical** to Scour 0.38.2 on 148/148 input
fixtures in the test suite (the 149th, `doctype.svg`, is rejected by
the new secure-by-default XML parser — opt-out via
`OptimizeOptions(allow_xml_entities=True)`). Reproduce locally with
`scripts/check_scour_baseline.py`.

`svg_regex.py` is derived from code by Enthought, Inc. (BSD 3-Clause).
Full attribution in [`NOTICE`](NOTICE).
