# Security guide

This page is the consumer-facing companion to [`SECURITY.md`](../SECURITY.md).
Read `SECURITY.md` first for the threat model and reporting procedure; this
page focuses on **how to use `svg_polish` safely** in real applications.

---

## TL;DR

* Defaults are safe. If you do nothing special, billion-laughs, XXE, and
  oversize inputs are rejected with `SvgSecurityError`.
* Catch `SvgSecurityError` (or its base, `SvgPolishError`) at the boundary
  where you process untrusted input.
* Do **not** flip `allow_xml_entities=True` globally.
* Prefer the default `minidom` backend over `lxml` for inputs from the public
  internet.

---

## Pattern: web server processing user uploads

```python
from svg_polish import optimize, SvgSecurityError, SvgParseError, SvgPolishError

def sanitize_uploaded_svg(blob: bytes) -> str:
    try:
        return optimize(blob)
    except SvgSecurityError:
        # Rejected by hardening — log and refuse the upload.
        raise UploadRejected("svg blocked by security policy")
    except SvgParseError:
        # Malformed input — typical user mistake.
        raise UploadRejected("not a valid svg")
    except SvgPolishError:
        # Anything else from svg_polish — treat as rejected.
        raise UploadRejected("svg could not be processed")
```

Catch the **specific** exceptions when you can act differently on each
(security vs. parse failure), and the broad `SvgPolishError` as a final
defensive net.

## Pattern: trusted pipeline that needs DOCTYPE entities

Some legacy SVG toolchains emit files with custom DOCTYPE entity definitions
for namespace shorthand. These are **not** automatically dangerous but are
indistinguishable from the billion-laughs vector at parse time.

If you control the upstream and the input is trusted:

```python
from svg_polish import optimize, OptimizeOptions  # OptimizeOptions in v1.0+

opts = OptimizeOptions(allow_xml_entities=True)
result = optimize(internal_svg, opts)  # emits SecurityWarning every call
```

Best practice:

* Enable the flag at the **call site**, not in a shared default object.
* Keep `SecurityWarning` visible in logs — it documents that this code path
  bypasses hardening.
* Pair with an upstream allow-list of trusted producers.

## Pattern: enforcing a tighter size limit

The default 100 MB limit is generous. For interactive endpoints you almost
certainly want something tighter:

```python
opts = OptimizeOptions(max_input_bytes=2 * 1024 * 1024)  # 2 MB
optimize(blob, opts)
```

This check runs **before** the parser allocates memory, so it costs O(1) for
`bytes` inputs and a single UTF-8 encode for `str` inputs.

## XML backend

v1.0 ships only the `defusedxml.minidom` backend, exposed as
`OptimizeOptions(xml_backend="minidom")` (the only accepted value). This is the
safest option for untrusted input: pure Python, no native code, the smallest
possible attack surface, and explicit rejection of every entity-expansion
class via defusedxml.

A v1.x release will add an opt-in `lxml` backend (3–5× faster on inputs over
~50 KB) behind the optional `svg-polish[fast]` extra. lxml is implemented in
C (libxml2 / libxslt), so even with `defusedxml[lxml]` enabled its attack
surface is materially larger than minidom's. When that backend ships, the
recommendation will remain: keep `minidom` for input arriving from the
public internet; switch to `lxml` only inside trusted pipelines that need
the throughput.

## What `svg_polish` does **not** do

* **It does not strip `<script>`, event handlers (`onclick=…`), or
  `xlink:href="javascript:…"`.** Those are XSS vectors when the SVG is later
  rendered inside HTML. If you embed user-supplied SVG in a web page, run a
  separate sanitizer such as [bleach](https://bleach.readthedocs.io/) or a
  Content-Security-Policy that disallows inline scripts.
* It does not validate that the optimized output is renderable in every
  browser. Lossless optimization preserves byte-equivalent rendering, but if
  the *input* relied on undefined behaviour, the *output* will too.
