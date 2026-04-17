# Migration from Scour

`svg_polish` is a v1.0 modernisation of
[Scour](https://github.com/scour-project/scour) v0.38.2. The
optimisation behaviour is the same; the public surface has been
rebuilt around a typed dataclass API.

This guide is for projects already using Scour or its low-level
`scour.scour` module.

## Installation

```bash
pip uninstall scour
pip install svg-polish
```

A `svg-polish[fast]` extra is reserved for the v1.x lxml-backed XML
engine; in v1.0 it currently installs no extra dependencies (the
`xml_backend="lxml"` option is not yet wired).

## CLI

The console script is renamed:

```bash
# Before
scour -i input.svg -o output.svg

# After
svg-polish -i input.svg -o output.svg
```

All CLI flags from Scour 0.38.2 still work, plus a few new ones
(`--decimal-engine`, future `--xml-backend`). Run `svg-polish --help`
for the current list.

## Python API

The recommended migration target is the typed `optimize` /
`OptimizeOptions` API:

```python
# Before — Scour low-level call
from scour.scour import scour_string, parse_args

options = parse_args(["--enable-viewboxing", "--shorten-ids"])
result = scour_string(svg_input, options)

# After — svg_polish typed API
from svg_polish import optimize, OptimizeOptions

opts = OptimizeOptions(enable_viewboxing=True, shorten_ids=True)
result = optimize(svg_input, opts)
```

`parse_args` and `scour_string` still live in
`svg_polish.optimizer` for internal use, but they accept the same
`OptimizeOptions` dataclass. They are not part of the supported public
surface — pin to `svg_polish.optimize_*` functions instead.

### Field mapping

Every CLI flag maps to one `OptimizeOptions` field:

| CLI flag | Field |
|---------|-------|
| `--set-precision=N` | `digits=N` |
| `--set-c-precision=N` | `cdigits=N` |
| `--disable-simplify-colors` | `simple_colors=False` |
| `--disable-style-to-xml` | `style_to_xml=False` |
| `--disable-group-collapsing` | `group_collapse=False` |
| `--create-groups` | `group_create=True` |
| `--keep-editor-data` | `keep_editor_data=True` |
| `--keep-unreferenced-defs` | `keep_defs=True` |
| `--no-renderer-workaround` | `renderer_workaround=False` |
| `--strip-xml-prolog` | `strip_xml_prolog=True` |
| `--remove-titles` | `remove_titles=True` |
| `--remove-descriptions` | `remove_descriptions=True` |
| `--remove-metadata` | `remove_metadata=True` |
| `--remove-descriptive-elements` | `remove_descriptive_elements=True` |
| `--enable-comment-stripping` | `strip_comments=True` |
| `--disable-embed-rasters` | `embed_rasters=False` |
| `--enable-viewboxing` | `enable_viewboxing=True` |
| `--indent=…` | `indent_type="space"\|"tab"\|"none"` |
| `--nindent=N` | `indent_depth=N` |
| `--no-line-breaks` | `newlines=False` |
| `--strip-xml-space` | `strip_xml_space_attribute=True` |
| `--enable-id-stripping` | `strip_ids=True` |
| `--shorten-ids` | `shorten_ids=True` |
| `--shorten-ids-prefix=P` | `shorten_ids_prefix="P"` |
| `--protect-ids-noninkscape` | `protect_ids_noninkscape=True` |
| `--protect-ids-list=…` | `protect_ids_list="…"` |
| `--protect-ids-prefix=P` | `protect_ids_prefix="P"` |
| `--error-on-flowtext` | `error_on_flowtext=True` |

## What's new in v1.0

- **Typed API** — `OptimizeOptions` (frozen dataclass), `OptimizeResult`,
  full exception hierarchy, `py.typed` marker.
- **`optimize`** — short canonical entry point; `optimize_string`,
  `optimize_bytes`, `optimize_path`, `optimize_async`,
  `optimize_with_stats` for specialised needs.
- **Secure-by-default** — `defusedxml` parses inputs by default; XXE,
  billion-laughs, external DTDs are rejected. `max_input_bytes`
  (100 MB default) bounds memory.
- **Float engine** — opt-in `decimal_engine="float"` for ~3–5× faster
  arithmetic on dense paths. Default stays `"decimal"` (lossless).
- **Thread-safe** — per-call thread-local `Decimal` precision context;
  concurrent calls with different `digits` are deterministic.
- **Modular internals** — the 4 700-line `scour.py` is split into
  single-purpose modules (`passes/path.py`, `dom.py`, `style.py`,
  `colors.py`, `ids.py`, …). `optimizer.py` is a ~600-line
  orchestrator.
- **Quality bar** — 660+ tests, 100 % line coverage, `mypy --strict`
  clean, `ruff` clean.

## Behavioural compatibility

For the same input and equivalent options (defaults vs. defaults), the
output is byte-exact with Scour 0.38.2 for over 159 fixture inputs in
the test suite. The only intentional differences:

- `APP` identifier in verbose output reads `svg-polish`.
- Version is `1.0.0` (independent versioning).
- `decimal_engine="float"` produces output that may differ in the
  last digit relative to Scour. This is the documented opt-in
  trade-off.

## Module mapping

| Scour module | `svg_polish` module |
|---|---|
| `scour.scour` | `svg_polish.optimizer` (orchestrator) plus the per-pass modules under `svg_polish.passes` |
| `scour.yocto_css` | `svg_polish.css` |
| `scour.svg_regex` | `svg_polish.svg_regex` |
| `scour.svg_transform` | `svg_polish.svg_transform` |
| `scour.scour.ScourStats` | `svg_polish.ScourStats` |

The new modules — `options`, `exceptions`, `dom`, `style`, `colors`,
`ids`, `groups`, `gradients`, `namespaces`, `serialize`, `cli` — are
internal but stable; refer to [`docs/architecture.md`](architecture.md)
for the layered design.
