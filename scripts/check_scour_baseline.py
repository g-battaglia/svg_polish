#!/usr/bin/env python3
"""Compare svg_polish output against the upstream Scour 0.38.2 baseline.

Run with Scour 0.38.2 importable on PYTHONPATH (or installed in the active
environment). Reads every input fixture under tests/fixtures/ as raw bytes
(skipping ``golden-*.svg`` which are *expected* outputs, not inputs) and
optimizes the same source through both:

* ``svg_polish.optimize`` with v1.0 defaults
* ``scour.scour.scourString`` with Scour defaults

Then reports byte-exact identity per fixture.

This script is the source of the documented compatibility claim
("byte-exact identical with Scour 0.38.2 on N/N input fixtures") and exists
so anyone auditing the fork can reproduce the verification on their own
machine. Usage::

    uv pip install --target /tmp/scour-baseline scour==0.38.2
    PYTHONPATH=/tmp/scour-baseline uv run python scripts/check_scour_baseline.py

The single expected divergence is ``doctype.svg``: svg_polish 1.0 rejects
DOCTYPE-bearing input by default through ``defusedxml`` (security feature,
opt-out via ``OptimizeOptions(allow_xml_entities=True)``). Scour 0.38.2
accepts it. That divergence is intentional and documented in SECURITY.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from scour.scour import scourString as scour_baseline  # type: ignore[import-not-found]
except ImportError:
    sys.stderr.write(
        "scour 0.38.2 is not importable.\n"
        "Install it into a throwaway dir and re-run with PYTHONPATH set:\n"
        "  uv pip install --target /tmp/scour-baseline scour==0.38.2\n"
        "  PYTHONPATH=/tmp/scour-baseline uv run python scripts/check_scour_baseline.py\n"
    )
    raise SystemExit(2)

from svg_polish import optimize as polish_optimize
from svg_polish.exceptions import SvgSecurityError

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def main() -> int:
    inputs = sorted(p for p in FIXTURES.glob("*.svg") if not p.name.startswith("golden-"))

    identical: list[str] = []
    different: list[tuple[str, int, int]] = []
    security_rejected: list[str] = []
    errors: list[tuple[str, str, str]] = []

    for fixture in inputs:
        raw = fixture.read_bytes()
        try:
            polish_out = polish_optimize(raw)
        except SvgSecurityError:
            security_rejected.append(fixture.name)
            continue
        except Exception as e:  # noqa: BLE001
            errors.append((fixture.name, "polish:" + type(e).__name__, str(e)[:120]))
            continue

        try:
            scour_out = scour_baseline(raw)
        except Exception as e:  # noqa: BLE001
            errors.append((fixture.name, "scour:" + type(e).__name__, str(e)[:120]))
            continue

        if polish_out == scour_out:
            identical.append(fixture.name)
        else:
            different.append((fixture.name, len(polish_out), len(scour_out)))

    total = len(inputs)
    compared = len(identical) + len(different)
    print(f"Total input fixtures:           {total}")
    print(f"Compared (both succeeded):      {compared}")
    pct = (len(identical) / compared * 100) if compared else 0.0
    print(f"  Byte-exact identical:         {len(identical):3d}  ({pct:.1f}% of compared)")
    print(f"  Different output:             {len(different):3d}")
    print(f"Security-rejected (expected):   {len(security_rejected)}")
    for name in security_rejected:
        print(f"  - {name}")
    print(f"Other errors:                   {len(errors)}")

    if different:
        print("\n=== DIVERGENT FIXTURES ===")
        for name, p_len, s_len in sorted(different):
            delta = p_len - s_len
            sign = "+" if delta >= 0 else ""
            print(f"  {name:60s} polish={p_len:6d}  scour={s_len:6d}  ({sign}{delta})")

    if errors:
        print("\n=== ERRORS ===")
        for name, err_type, err_msg in errors:
            print(f"  {name}: {err_type}: {err_msg}")

    # Exit non-zero if we got unexpected divergences or errors so CI catches drift.
    return 0 if (not different and not errors) else 1


if __name__ == "__main__":
    raise SystemExit(main())
