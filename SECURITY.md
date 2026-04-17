# Security policy

`svg_polish` is **secure by default**: every public entry point parses untrusted
SVG/XML through [`defusedxml`](https://github.com/tiran/defusedxml) and refuses
to expand XML entities, follow external references, or accept arbitrarily large
inputs unless the caller explicitly opts in.

This document describes the threat model, the protections implemented, and how
to report a security issue.

---

## Threat model

`svg_polish` is intended to be safe to run on **untrusted SVG content**, such as
files received over the network, uploaded by users of a web application, or
extracted from third-party archives. The library defends against the following
threat vectors:

| Vector | Description | Default handling |
|---|---|---|
| **Billion laughs** | Exponential entity expansion DoS via nested `<!ENTITY>` definitions. | Rejected — `SvgSecurityError` |
| **XXE — file disclosure** | `<!ENTITY xxe SYSTEM "file:///etc/passwd">` reads local files. | Rejected — `SvgSecurityError` |
| **XXE — SSRF** | External entity referencing `http://attacker.example/...`. | Rejected — `SvgSecurityError` |
| **Parameter-entity DTD attacks** | `<!ENTITY % param SYSTEM "...">` chained DTDs. | Rejected — `SvgSecurityError` |
| **Oversize input** | Memory exhaustion via multi-gigabyte inputs. | Rejected over `100 MB` — `SvgSecurityError` |
| **Malformed XML** | Crafted unparseable input crashing the host. | Wrapped in `SvgParseError` (no stack trace leak) |

The library does **not** attempt to defend against:

* Arbitrary code execution from the host runtime (out of scope — the parser is
  pure Python and `defusedxml` does not exec user content).
* Attacks against downstream renderers that consume the optimized SVG. Once
  `svg_polish` returns a string, sanitisation for display (e.g. stripping
  `<script>` for HTML embedding) is the consumer's responsibility.
* Side-channel attacks (timing, cache) — there are no cryptographic operations
  in the optimization pipeline.

---

## Protections in detail

### 1. `defusedxml` is a hard runtime dependency

Every parse goes through `defusedxml.minidom.parseString`. There is no way to
disable defusedxml at install time. The dependency is pure Python with zero
native code, so it adds no measurable overhead on the hot path.

### 2. `OptimizeOptions.allow_xml_entities = False` by default

Inputs containing `<!ENTITY ...>` definitions, external references, or
DOCTYPE-with-entities are rejected with :class:`svg_polish.SvgSecurityError`.

This is the **only** intentional behavioural divergence from upstream Scour
0.38.2. With this opt-out enabled the optimizer is byte-exact identical to
Scour 0.38.2 on every other fixture in the test suite (148/148 inputs verified
via `scripts/check_scour_baseline.py`).

To opt out (e.g. for trusted internal pipelines that must preserve a custom
DOCTYPE), pass `allow_xml_entities=True`. A `SecurityWarning` is emitted on
every call so the choice is visible in logs.

```python
from svg_polish import optimize, OptimizeOptions  # OptimizeOptions in v1.0+

opts = OptimizeOptions(allow_xml_entities=True)
result = optimize(svg, opts)  # warns once per call
```

### 3. `OptimizeOptions.max_input_bytes = 100 * 1024 * 1024`

Inputs larger than 100 MB are rejected before the parser allocates memory for
the DOM tree. Override with any positive integer, or pass `None` (programmatic)
or `-1` (CLI) to disable the check entirely.

We picked 100 MB as a default that covers virtually every legitimate SVG
workload while making memory-exhaustion attacks impractical.

### 4. Typed exception hierarchy

* `SvgSecurityError` — rejected by the secure-by-default checks.
* `SvgParseError` — XML/SVG could not be parsed. Carries `line`, `column`, and
  a **truncated** (≤ 80 char) `snippet` so logs never echo large untrusted
  payloads.

Both inherit `SvgPolishError`, so a single `except SvgPolishError` catches
every library-specific failure.

---

## Recommendations for consumers

* **Server-side / SaaS**: keep all defaults. Catch `SvgSecurityError` and
  reject the upload with a 4xx response.
* **Trusted pipelines**: if you must process inputs that legitimately use
  DOCTYPE entities, set `allow_xml_entities=True` on a per-call basis — never
  globally.
* **`xml_backend="lxml"` (extra `[fast]`)**: the lxml backend is implemented
  in C. Even with `defusedxml[lxml]` enabled, lxml's attack surface is larger
  than `xml.dom.minidom`'s. Prefer the default `minidom` backend for inputs
  arriving from the public internet.
* Always cap input at the application boundary (e.g. nginx
  `client_max_body_size`) **in addition to** `max_input_bytes`. Defence in
  depth is cheap.

---

## Reporting a vulnerability

Please open a private security advisory via GitHub:

> https://github.com/g-battaglia/svg_polish/security/advisories/new

Do **not** file public issues for security problems. We will respond within
five business days and coordinate disclosure once a fix is ready.
