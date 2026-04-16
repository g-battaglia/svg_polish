# Migration from Scour

SVG Polish is a fork of [Scour](https://github.com/scour-project/scour). This guide helps you migrate from Scour to SVG Polish.

## Installation

Replace Scour with SVG Polish:

```bash
# Remove Scour
pip uninstall scour

# Install SVG Polish
pip install svg-polish
```

## CLI Changes

The CLI command changes from `scour` to `svg-polish`:

```bash
# Before (Scour)
scour -i input.svg -o output.svg

# After (SVG Polish)
svg-polish -i input.svg -o output.svg
```

All CLI flags are identical. No changes needed to your arguments.

## Python API Changes

### Import Changes

```python
# Before (Scour)
from scour.scour import scourString, parse_args
from scour import scour

# After (SVG Polish) - recommended
from svg_polish import optimize, optimize_file

# After (SVG Polish) - low-level, same API as Scour
from svg_polish.optimizer import scourString, parse_args
```

### New High-Level API

SVG Polish adds a cleaner API that didn't exist in Scour:

```python
# Simple optimization (new!)
from svg_polish import optimize
result = optimize(svg_string)

# File optimization (new!)
from svg_polish import optimize_file
result = optimize_file("input.svg")
```

### Low-Level API (unchanged)

The low-level API is identical to Scour:

```python
from svg_polish.optimizer import scourString, parse_args

options = parse_args(["--enable-viewboxing", "--shorten-ids"])
result = scourString(svg_input, options)
```

## Module Mapping

| Scour Module | SVG Polish Module |
|-------------|-------------------|
| `scour.scour` | `svg_polish.optimizer` |
| `scour.yocto_css` | `svg_polish.css` |
| `scour.svg_regex` | `svg_polish.svg_regex` |
| `scour.svg_transform` | `svg_polish.svg_transform` |
| `scour.scour.ScourStats` | `svg_polish.stats.ScourStats` |

## Function Mapping

All functions in `svg_polish.optimizer` have the same names and signatures as in `scour.scour`:

| Function | Status |
|----------|--------|
| `scourString()` | Unchanged |
| `scourXmlFile()` | Unchanged |
| `parse_args()` | Unchanged |
| `start()` | Unchanged |
| `run()` | Unchanged |

## What Changed Internally

- **Python 2 support removed** - No more `six`, `__future__` imports, or Python 2 workarounds
- **`distutils` replaced** - `distutils.spawn` replaced with `shutil.which` (removed in Python 3.12)
- **Type annotations added** - All public functions have type hints
- **`py.typed` marker** - Type checkers recognize SVG Polish types
- **`ScourStats` moved** - From inline class in `scour.py` to `svg_polish.stats`
- **Test coverage** - 100% coverage (Scour had ~70%)

## Behavioral Differences

SVG Polish produces **identical output** to Scour for the same input and options. The optimization algorithm is unchanged.

The only differences are:
- The `APP` identifier in verbose output reads `svg-polish` instead of `scour`
- The version number is `1.0.0` (independent of Scour's versioning)

## Compatibility

- **Python:** 3.10+ (Scour supported Python 2.7 and 3.x)
- **Dependencies:** Zero runtime dependencies (same as Scour after removing `six`)
- **Output:** Byte-identical to Scour for the same input and options
