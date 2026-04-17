# SVG Polish Documentation

`svg_polish` is a fast, lossless, type-safe SVG optimizer for Python.
It strips editor metadata, collapses redundant attributes, deduplicates
gradients, optimises path data and transforms — while guaranteeing the
output renders identically to the input. The library is fully typed
(`py.typed`), thread-safe, and secure-by-default against XML attacks.

## Contents

- [Getting Started](getting-started.md) — installation, first steps,
  quick examples.
- [Python API Reference](api.md) — `optimize`, `optimize_path`,
  `OptimizeOptions`, `OptimizeResult`, exceptions.
- [Configuration Guide](configuration.md) — every `OptimizeOptions`
  field with presets.
- [CLI Reference](cli.md) — every command-line flag.
- [Optimization Guide](optimizations.md) — what `svg_polish` rewrites
  and how.
- [Performance](performance.md) — when to flip `decimal_engine`,
  `xml_backend`, `digits`; benchmark workflow.
- [Security](security.md) — usage patterns for untrusted input.
- [Architecture](architecture.md) — module layout, layered design,
  pipeline.
- [Contributing](contributing.md) — development setup, test suites,
  PR checklist.
- [Migration from Scour](migration.md) — how to port code from Scour
  0.38.2 to the v1.0 typed API.

## Quick Links

- [GitHub Repository](https://github.com/g-battaglia/svg_polish)
- [PyPI Package](https://pypi.org/project/svg-polish/)
- [Changelog](../CHANGELOG.md)
- [Security Policy](../SECURITY.md)
- [License](../LICENSE) (Apache 2.0)
