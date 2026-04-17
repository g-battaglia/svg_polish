# Architecture

`svg_polish` is organised as a small core orchestrator that walks the
DOM, plus a set of single-purpose modules that own one transformation
pass each. Everything is deliberately layered so that a contributor can
read one module without holding the rest of the codebase in their head.

## Module layout

```
src/svg_polish/
├── __init__.py        # Public API: optimize*, OptimizeOptions, OptimizeResult, exceptions
├── options.py         # OptimizeOptions dataclass + validation
├── exceptions.py      # SvgPolishError hierarchy
├── stats.py           # ScourStats dataclass
├── constants.py       # SVG namespaces, lexicons, default attribute tables
├── types.py           # Shared aliases + thread-local Decimal precision context
│
├── cli.py             # CLI: argparse/optparse, file I/O, console entry point
│
├── optimizer.py       # Pipeline orchestrator (scour_string, scour_xml_file)
├── serialize.py       # Custom XML serializer (tighter than minidom's toxml())
├── dom.py             # DOM helpers: ID maps, url(#…) reference walker
├── style.py           # CSS-on-attributes repair, style inheritance helpers
├── colors.py          # CSS color parsing + shortest-form conversion
├── ids.py             # ID shortening, dead-ID removal
├── namespaces.py      # Namespace pruning + prefix remap
├── groups.py          # <g> collapse / sibling merge / common-attr promotion
├── gradients.py       # Linear/radial gradient deduplication
│
├── passes/            # One module per optimisation pass
│   ├── __init__.py
│   ├── path.py        # clean_path: 8-phase path data optimisation
│   ├── transform.py   # optimise transform/patternTransform/gradientTransform
│   ├── length.py      # scour_unitless_length + reduce_precision walker
│   ├── attributes.py  # remove_unused_attributes_on_parent
│   ├── defaults.py    # remove_default_attribute_values
│   ├── comments.py    # strip_comments
│   ├── rasters.py     # embed_rasters (lazy urllib import)
│   └── sizing.py      # properly_size_doc, viewBox conversion
│
├── svg_regex.py       # Path data lexer + recursive-descent parser
├── svg_transform.py   # Transform attribute lexer + parser
├── css.py             # Minimal CSS parser for <style> elements
└── py.typed           # PEP 561 marker
```

## Layering

Modules import only from layers below them; circular imports are
forbidden by mypy and CI. From bottom to top:

1. **Foundation** — `constants`, `types`, `exceptions`, `options`,
   `stats`. Pure data, no DOM. Always importable.
2. **Parsers** — `svg_regex`, `svg_transform`, `css`. Pure functions
   over text, return typed structures. Read `_precision.engine` to
   choose between `Decimal` and `float`.
3. **DOM helpers** — `dom`, `style`, `colors`, `namespaces`,
   `serialize`. Operate on `xml.dom.minidom` nodes. No optimisation
   logic.
4. **Structural passes** — `ids`, `groups`, `gradients`. Move/merge
   nodes; consume DOM helpers.
5. **Numeric / textual passes** — `passes/*`. Operate on attribute
   values, may call parsers and length scouring.
6. **Orchestrator** — `optimizer.scour_string`. Wires everything
   inside a `precision_scope(...)` so the per-call precision is
   thread-local.
7. **Surface** — `__init__.py` exposes `optimize_*`,
   `OptimizeOptions`, `OptimizeResult`, the exception hierarchy.
   `cli.py` adds the console entry point.

## Optimisation pipeline

`scour_string` runs the passes in this order:

1. Parse XML (`defusedxml.minidom.parseString`, secure by default).
2. Strip editor-specific data unless `keep_editor_data=True`.
3. Repair styles (canonicalise attributes vs. `style="…"`).
4. Convert colors to shortest form (`#ff0000` → `red`).
5. Remove unreferenced `<defs>` content.
6. Remove empty containers (`<defs>`, `<g>`, `<metadata>`).
7. Promote common attributes to the parent group.
8. Collapse `<g>` elements where safe.
9. Merge sibling groups with identical attributes.
10. Optionally create new groups for runs of identical attributes.
11. Re-promote common attributes to the new groups.
12. Optimise path data (`passes/path.py`).
13. Reduce numeric precision on length attributes (`passes/length.py`).
14. Strip default attribute values (`passes/defaults.py`).
15. Optimise transform attributes (`passes/transform.py`).
16. Shorten IDs if requested (`ids.shorten_ids`).
17. Convert to viewBox if requested (`passes/sizing.py`).
18. Serialise to text (`serialize.py`).

### Path data sub-pipeline (`clean_path`)

Inside `passes/path.py`, the 8-phase pipeline:

1. Convert all commands to relative coordinates.
2. Remove zero-length segments.
3. Remove no-op commands.
4. Convert straight cubic curves to lines.
5. First collapse: merge runs of the same command type.
6. Convert `l dx 0` to `h dx`, `l 0 dy` to `v dy`.
7. Convert `c` to `s` where the first control point is the
   reflection of the previous segment's last control point.
8. Collapse consecutive same-direction segments.

The output is only kept if it is strictly shorter than the input — a
safety net against pathological inputs.

## Concurrency

`scour_string` is reentrant *and* thread-safe. The numeric precision
state (`_precision.ctx`, `_precision.ctx_c`, `_precision.engine`)
lives on a `threading.local`, and `precision_scope(...)` saves/restores
the previous values around each call. A `ThreadPoolExecutor` running
many calls with different `digits` settings produces deterministic,
byte-exact output per call.

`optimize_async` exists exactly for this use case: it offloads a
synchronous `optimize_string` invocation to a worker via
`asyncio.to_thread`, so async web frameworks can call into the
optimiser without blocking the event loop.

## Numeric engines

By default the path / transform parsers return `Decimal`, and
arithmetic in the passes uses `Decimal` end-to-end. This is the
**lossless** engine — the output renders identically to the input.

`OptimizeOptions(decimal_engine="float")` switches the parsers to
return native `float` for ~3-5× faster arithmetic on dense paths. The
trade-off is documented in `docs/performance.md`: the output may differ
in the last digit and is no longer byte-exact across machines.

## Security posture

Inputs are parsed with `defusedxml`, so XXE, billion-laughs, external
DTD fetches, and similar entity-expansion attacks are rejected by
default. `OptimizeOptions.allow_xml_entities=True` falls back to the
permissive parser and emits a `SecurityWarning` — only enable on
trusted input. Inputs larger than `OptimizeOptions.max_input_bytes`
(100 MB by default) are rejected with `SvgSecurityError`. See
`docs/security.md` for the full threat model.

## Why custom serialisation?

`minidom.Document.toxml()` produces verbose output with unnecessary
whitespace, sometimes losing namespace declarations, and is
indifferent to attribute ordering. `serialize.py` produces tighter
output, sorts attributes deterministically, and applies SVG-specific
shortcut rules (e.g. self-closing tags for empty elements).

## Why `# pragma: no cover` on a few lines?

A handful of branches are unreachable under the current control flow
but are kept as defensive code:

- `default_attributes_universal` loop — the list is always empty.
- `remap_namespace_prefix` with a non-empty prefix — always `""`.
- ViewBox `ValueError` catch — values are scoured upstream.
- `xmlns:` prefix in serialisation — minidom always includes `xmlns`
  in `nodeName`.
- `str.split()` returning an empty list — impossible per Python spec.

These are documented in-line and excluded from coverage so they don't
mask genuine gaps.
