"""Session-scoped fixtures for the benchmark suite.

Generates dense SVG documents (many ``<path>``, ``<g>``, and ``<style>``
elements) at session start so the benchmark loop only times the
optimisation pipeline, never fixture I/O. Names describe the *profile*
(``dense-chart``, ``dense-paths``) rather than any external consumer —
the library must remain agnostic of where its inputs come from.

The generator is deterministic (seeded ``random.Random``) so benchmark
runs are reproducible across machines and against historical baselines
saved by ``poe bench``.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

import pytest


def _build_dense_chart(target_bytes: int, seed: int) -> str:
    """Synthesise an SVG that resembles a chart-style render.

    Mixes ``<g>`` containers, transform attributes, ``<path>`` elements
    with cubic Bézier runs, ``<rect>`` axes, and a ``<style>`` block —
    the combination exercises the path/transform/style/group passes
    together. The output grows in 5-element batches until it crosses
    *target_bytes*; sub-100-byte tail variation is acceptable.
    """
    rng = random.Random(seed)
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="800" height="600" viewBox="0 0 800 600">\n'
        "<style>\n"
        "  .axis { stroke: #333333; stroke-width: 1.5; fill: none; }\n"
        "  .grid { stroke: #cccccc; stroke-width: 0.5; }\n"
        "  .series-a { stroke: #ff6600; stroke-width: 2.0; fill: none; }\n"
        "  .series-b { stroke: #0066ff; stroke-width: 2.0; fill: none; }\n"
        "  .series-c { stroke: #66cc00; stroke-width: 2.0; fill: none; }\n"
        "  .label { font-family: sans-serif; font-size: 11px; fill: #666666; }\n"
        "</style>\n"
    )
    body_chunks: list[str] = []
    size = len(head) + len("</svg>\n")
    series = ("series-a", "series-b", "series-c")
    while size < target_bytes:
        x = rng.uniform(0, 800)
        y = rng.uniform(0, 600)
        cls = series[rng.randrange(len(series))]
        translate_x = rng.uniform(-50, 50)
        translate_y = rng.uniform(-50, 50)
        scale = rng.uniform(0.85, 1.15)
        rotate = rng.uniform(-15, 15)
        # Build a cubic Bézier polyline with 6 segments — enough nodes to
        # exercise scour_path's collinearity, control-point precision,
        # and relative-conversion branches.
        path_d_parts = [f"M{x:.4f} {y:.4f}"]
        for _ in range(6):
            cx1 = x + rng.uniform(-30, 30)
            cy1 = y + rng.uniform(-30, 30)
            cx2 = x + rng.uniform(-30, 30)
            cy2 = y + rng.uniform(-30, 30)
            x = x + rng.uniform(-40, 40)
            y = y + rng.uniform(-40, 40)
            path_d_parts.append(f"C{cx1:.4f} {cy1:.4f} {cx2:.4f} {cy2:.4f} {x:.4f} {y:.4f}")
        path_d = " ".join(path_d_parts)
        chunk = (
            f'<g transform="translate({translate_x:.3f},{translate_y:.3f}) '
            f'scale({scale:.4f}) rotate({rotate:.3f})">\n'
            f'  <path class="{cls}" d="{path_d}"/>\n'
            f'  <rect class="grid" x="{x:.2f}" y="{y:.2f}" width="20" height="20" '
            f'fill="none"/>\n'
            f"</g>\n"
        )
        body_chunks.append(chunk)
        size += len(chunk)
    return head + "".join(body_chunks) + "</svg>\n"


def _build_dense_paths(target_bytes: int, seed: int) -> str:
    """Synthesise an SVG dominated by raw ``<path>`` data with no grouping.

    Stresses the path parser, ``clean_path`` pipeline, and
    ``scour_unitless_length`` rounding without the overhead of ``<g>``
    containers or shared style sheets — useful for isolating numeric
    optimisation from structural optimisation.
    """
    rng = random.Random(seed)
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="1024" height="768" viewBox="0 0 1024 768">\n'
    )
    body_chunks: list[str] = []
    size = len(head) + len("</svg>\n")
    while size < target_bytes:
        # Mix of M/L/C/Q/Z commands across one path; arcs are more
        # expensive to scour, included sparingly.
        cmds: list[str] = []
        x = rng.uniform(0, 1024)
        y = rng.uniform(0, 768)
        cmds.append(f"M{x:.5f} {y:.5f}")
        for i in range(15):
            kind = rng.choice("LLCQA")
            if kind == "L":
                x = x + rng.uniform(-20, 20)
                y = y + rng.uniform(-20, 20)
                cmds.append(f"L{x:.5f} {y:.5f}")
            elif kind == "C":
                cx1, cy1 = rng.uniform(-30, 30), rng.uniform(-30, 30)
                cx2, cy2 = rng.uniform(-30, 30), rng.uniform(-30, 30)
                x = x + rng.uniform(-25, 25)
                y = y + rng.uniform(-25, 25)
                cmds.append(f"C{x + cx1:.5f} {y + cy1:.5f} {x + cx2:.5f} {y + cy2:.5f} {x:.5f} {y:.5f}")
            elif kind == "Q":
                qcx, qcy = rng.uniform(-25, 25), rng.uniform(-25, 25)
                x = x + rng.uniform(-20, 20)
                y = y + rng.uniform(-20, 20)
                cmds.append(f"Q{x + qcx:.5f} {y + qcy:.5f} {x:.5f} {y:.5f}")
            elif kind == "A" and i % 5 == 0:
                rx = rng.uniform(2, 8)
                ry = rng.uniform(2, 8)
                x = x + rng.uniform(-15, 15)
                y = y + rng.uniform(-15, 15)
                cmds.append(f"A{rx:.4f} {ry:.4f} 0 0 1 {x:.5f} {y:.5f}")
        cmds.append("Z")
        d_attr = " ".join(cmds)
        fill = f"#{rng.randrange(0, 0x1000000):06x}"
        chunk = f'<path d="{d_attr}" fill="{fill}" fill-opacity="0.85"/>\n'
        body_chunks.append(chunk)
        size += len(chunk)
    return head + "".join(body_chunks) + "</svg>\n"


# Map of fixture name → (builder, target byte size). Names describe the
# profile (dense-chart, dense-paths) plus an order-of-magnitude size hint
# — they MUST stay neutral and never reference any specific consumer.
_FIXTURES: dict[str, tuple[Callable[[int, int], str], int, int]] = {
    "dense-chart-50kb.svg": (_build_dense_chart, 50 * 1024, 0xC0FFEE),
    "dense-chart-100kb.svg": (_build_dense_chart, 100 * 1024, 0xBADCAFE),
    "dense-paths-medium.svg": (_build_dense_paths, 60 * 1024, 0xFEEDFACE),
}


@pytest.fixture(scope="session")
def benchmark_fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Materialise the dense SVG fixtures into a session tmpdir.

    Generated once per pytest session; each benchmark test reads its
    fixture once via ``Path.read_text`` so the timed call sees only the
    optimiser. Returns a mapping of *fixture name* → *file path*.
    """
    out_dir = tmp_path_factory.mktemp("svg_bench_fixtures")
    paths: dict[str, Path] = {}
    for name, (builder, size, seed) in _FIXTURES.items():
        text = builder(size, seed)
        target = out_dir / name
        target.write_text(text)
        paths[name] = target
    return paths
