"""Optimisation passes invoked by the orchestrator in :mod:`svg_polish.optimizer`.

A "pass" is a self-contained transformation that walks part of the DOM
and rewrites it in place. Each module here owns one pass (or a tightly
coupled cluster of passes) and exposes the public functions the
orchestrator calls — no shared state, no implicit ordering, no
back-pointers to ``optimizer.py``. This keeps the orchestrator a thin
sequencer over independent transformations.

Modules in this package:

* :mod:`~svg_polish.passes.attributes` — drop inheritable attributes
  the children don't actually use.
* :mod:`~svg_polish.passes.defaults` — drop attributes whose value
  equals the SVG/CSS default.
* :mod:`~svg_polish.passes.comments` — strip XML comments.
* :mod:`~svg_polish.passes.rasters` — embed external raster images
  as data URIs (lazy-imports ``urllib`` since it's only opt-in).
* :mod:`~svg_polish.passes.sizing` — compute the right ``width`` /
  ``height`` / ``viewBox`` for the document element.
* :mod:`~svg_polish.passes.path` — clean and re-encode ``<path>``
  ``d=""`` data (the largest pass — coordinate normalisation,
  arc/cubic/quad simplifications, command coalescing).
* :mod:`~svg_polish.passes.transform` — minimise ``transform=""``
  matrices and decompose them into shorter equivalent forms.
"""
