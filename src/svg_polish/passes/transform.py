"""Optimisation of ``transform``, ``patternTransform``, ``gradientTransform`` attrs.

Three layers of work:

* :func:`optimize_angle` — normalise an angle to ``[-90, 270)`` so
  the textual representation is as short as possible. Negatives and
  large positives both cost an extra char (``-`` or three-digit form).
* :func:`optimize_transform` — operate on a parsed transform list
  (``[(name, [args]), …]``) and:
    1. recover named transforms from a single ``matrix(…)`` (identity,
       translation, scale, rotation);
    2. drop trailing default arguments (``translate(x,0)`` → ``translate(x)``,
       ``rotate(a,0,0)`` → ``rotate(a)``, ``scale(s,s)`` → ``scale(s)``);
    3. coalesce consecutive same-type runs (``translate translate``,
       ``rotate rotate``, ``scale scale``);
    4. drop identity tail items (``rotate(0)``, ``skewX(0)``, …).
* :func:`optimize_transforms` — DOM walker that runs the parser →
  optimiser → serialiser pipeline for every transform attribute on
  every element in a subtree, committing the result only when it
  shortens the original.

The pass relies on :mod:`svg_polish.passes.length` for numeric
serialisation (``scour_unitless_length``) and on
:mod:`svg_polish.svg_transform` for parsing the input string into a
typed list. Matrix × matrix multiplication is intentionally not
implemented — see the ``FIXME`` in :func:`optimize_transform`.
"""

from __future__ import annotations

import math
import optparse
from decimal import Decimal
from typing import cast
from xml.dom import Node
from xml.dom.minidom import Element

from svg_polish.passes.length import scour_unitless_length
from svg_polish.svg_transform import svg_transform_parser
from svg_polish.types import TransformData

__all__ = [
    "optimize_angle",
    "optimize_transform",
    "optimize_transforms",
    "serialize_transform",
]


def serialize_transform(transformObj: TransformData) -> str:
    """Serialise a parsed transform list back to its ``transform=""`` form.

    Joins each ``(name, args)`` tuple as ``name(arg1 arg2 …)`` with
    a single space between items. Args are emitted via
    :func:`scour_unitless_length` so they pick up the configured
    precision and the leading-zero / scientific-notation rules.
    """
    return " ".join(
        command + "(" + " ".join(scour_unitless_length(number) for number in numbers) + ")"
        for command, numbers in transformObj
    )


def optimize_angle(angle: Decimal) -> Decimal:
    """Normalise *angle* to ``[-90, 270)`` for the shortest text form.

    Any rotation can be expressed within a 360-degree window of any
    starting point. Negative angles add a leading ``-``; angles
    ≥ 100 add a third digit. The chosen window ``[-90, 270)`` is
    one of the two equivalent picks (``(-100, 260]`` is the other)
    that minimises both costs together.
    """
    # Python's ``%`` keeps the sign of the divisor, so use ``-360``
    # for negative dividends to preserve the sign of the angle.
    if angle < 0:
        angle %= -360
    else:
        angle %= 360
    if angle >= 270:
        angle -= 360
    elif angle < -90:
        angle += 360
    return angle


def optimize_transform(transform: TransformData) -> None:
    """Simplify *transform* in place using four ordered passes.

    ``transform`` is a list of ``(name, [Decimal args])`` produced by
    :data:`svg_polish.svg_transform.svg_transform_parser`. The
    function mutates it.

    1. **Single-matrix recovery** — when *transform* contains exactly
       one ``matrix(a b c d e f)``, attempt to rewrite it as a
       shorter named form: identity (delete), translation, uniform/
       non-uniform scale, or rotation about the origin.
    2. **Drop default args** — ``translate(x,0)`` → ``translate(x)``;
       ``rotate(a,0,0)`` → ``rotate(a)``; ``scale(s,s)`` → ``scale(s)``.
       ``rotate``'s angle is also re-normalised via
       :func:`optimize_angle`.
    3. **Coalesce same-type runs** — adjacent ``translate``/``rotate``/
       ``scale`` pairs combine into one (with the appropriate
       arithmetic). Identity results are dropped immediately.
    4. **Drop tail identities** — single-element ``rotate(0)`` /
       ``skewX(0)`` / ``skewY(0)`` left behind by the previous pass.

    Matrix-times-matrix coalescing is not implemented (see the FIXME
    in the body); a fully general matrix decomposition would handle
    cases like ``matrix(0 1 -1 0 0 0) rotate(180) scale(-1)`` →
    ``rotate(90)``, but the inverse trig is fragile under rounding.
    """
    # FIXME: reordering would catch more cases:
    #   1) coalesce same-type runs first
    #   2) attempt matrix-form recovery on remaining single matrices
    #   3) drop default args
    # Each combo of (matrix form, named form) of the same effective
    # rotation/scale would be normalised to the same canonical form.

    # Single-matrix → named transform.
    # SVG's matrix(a b c d e f) maps to:
    # | a c e |     | A1 A2 A3 |
    # | b d f |  =  | B1 B2 B3 |
    # | 0 0 1 |     |  0  0  1 |
    if len(transform) == 1 and transform[0][0] == "matrix":
        matrix = A1, B1, A2, B2, A3, B3 = transform[0][1]
        # Identity:
        # | 1 0 0 |
        # | 0 1 0 |
        if matrix == [1, 0, 0, 1, 0, 0]:
            del transform[0]
        # Translation by (X, Y):
        # | 1 0 X |
        # | 0 1 Y |
        elif A1 == 1 and A2 == 0 and B1 == 0 and B2 == 1:
            transform[0] = ("translate", [A3, B3])
        # Scale by (X, Y):
        # | X 0 0 |
        # | 0 Y 0 |
        elif A2 == 0 and A3 == 0 and B1 == 0 and B3 == 0:
            transform[0] = ("scale", [A1, B2])
        # Rotation by angle A about the origin (clockwise, degrees):
        # | cos -sin 0 |
        # | sin  cos 0 |
        elif (
            A1 == B2
            and -1 <= A1 <= 1
            and A3 == 0
            and -B1 == A2
            and -1 <= B1 <= 1
            and B3 == 0
            # cos² + sin² ≈ 1 with rounded decimals; use a hard
            # epsilon. FIXME: should scale with the precision of
            # the (sin|cos)_A inputs, not be a constant 1e-15.
            # ``1e-15`` is a Python float literal; comparing against ``A1``/``B1``
            # works whether they are ``Decimal`` (decimal engine) or ``float``
            # (float engine) — we coerce the LHS to match the RHS type.
            and abs(float((B1**2) + (A1**2) - 1)) < 1e-15
        ):
            sin_A, cos_A = B1, A1
            # asin/acos each cover only 180° of the unit circle;
            # the (sign sin, sign cos) pair tells us which quadrant
            # we're in:
            #  --  → A < -90    -+ → -90..0
            #  ++  → 0..90       +- → A ≥ 90
            #
            # asin gives the right answer in the middle two
            # quadrants; the outer two need flipping around 180°.
            A_decimal = Decimal(str(math.degrees(math.asin(float(sin_A)))))
            # Match the engine: rebuild as float when the matrix args are floats
            # so subsequent arithmetic stays type-consistent.
            A = cast("Decimal", float(A_decimal)) if not isinstance(sin_A, Decimal) else A_decimal
            if cos_A < 0:
                A = -180 - A if sin_A < 0 else 180 - A
            transform[0] = ("rotate", [A])

    # Drop trailing default arguments.
    for type, args in transform:
        if type == "translate":
            # translate(x, 0) → translate(x).
            if len(args) == 2 and args[1] == 0:
                del args[1]
        elif type == "rotate":
            args[0] = optimize_angle(args[0])
            # rotate(a, 0, 0) → rotate(a).
            if len(args) == 3 and args[1] == args[2] == 0:
                del args[1:]
        elif type == "scale" and len(args) == 2 and args[0] == args[1]:
            # scale(s, s) → scale(s) (uniform scale).
            del args[1]

    # Coalesce adjacent same-type transforms. Identity skewX/skewY
    # are dropped in the next loop, not here, because they don't
    # combine with each other.
    # FIXME: matrix × matrix multiplication would be safe to fold in
    # this same loop.
    i = 1
    while i < len(transform):
        currType, currArgs = transform[i]
        prevType, prevArgs = transform[i - 1]
        if currType == prevType == "translate":
            prevArgs[0] += currArgs[0]
            # The second translate may omit y; only fold y if both sides have it.
            if len(currArgs) == 2:
                if len(prevArgs) == 2:
                    prevArgs[1] += currArgs[1]
                elif len(prevArgs) == 1:
                    prevArgs.append(currArgs[1])
            del transform[i]
            if prevArgs[0] == prevArgs[1] == 0:
                # Sum was identity — drop the merged result too.
                i -= 1
                del transform[i]
        elif currType == prevType == "rotate" and len(prevArgs) == len(currArgs) == 1:
            # Only origin-rotation pairs commute additively.
            # Centred rotations (3-arg) don't, so leave them alone.
            prevArgs[0] = optimize_angle(prevArgs[0] + currArgs[0])
            del transform[i]
        elif currType == prevType == "scale":
            prevArgs[0] *= currArgs[0]
            # Handle the implicit-y forms in either operand.
            if len(prevArgs) == 2 and len(currArgs) == 2:
                prevArgs[1] *= currArgs[1]
            elif len(prevArgs) == 1 and len(currArgs) == 2:
                # prev is uniform; promote it to (sx, sx) and apply currArgs[1].
                prevArgs.append(prevArgs[0] * currArgs[1])
            elif len(prevArgs) == 2 and len(currArgs) == 1:
                prevArgs[1] *= currArgs[0]
            del transform[i]
            # Unit scale [1] or [1, 1] → drop.
            if prevArgs[0] == 1 and (len(prevArgs) == 1 or prevArgs[1] == 1):
                i -= 1
                del transform[i]
        else:
            i += 1

    # Drop tail identities the coalesce loop couldn't see (single
    # transforms without a predecessor to merge with).
    i = 0
    while i < len(transform):
        currType, currArgs = transform[i]
        if currType in ("skewX", "skewY", "rotate") and len(currArgs) == 1 and currArgs[0] == 0:
            del transform[i]
        else:
            i += 1


def optimize_transforms(element: Element, options: optparse.Values) -> int:
    """Walk *element*'s subtree minimising every transform attribute.

    For each of ``transform``, ``patternTransform``,
    ``gradientTransform`` on each element: parse, optimise, serialise,
    then commit only if the new string is strictly shorter than the
    original (or empty, in which case the attribute is removed).

    Recurses into element children. The *options* parameter is
    accepted for signature parity with the rest of the pipeline but
    is currently unused — the optimiser's behaviour is fully
    determined by the parsed transform itself.

    Returns the total bytes saved across the subtree.
    """
    num = 0

    for transformAttr in ["transform", "patternTransform", "gradientTransform"]:
        val = element.getAttribute(transformAttr)
        if val:
            transform = svg_transform_parser.parse(val)

            optimize_transform(transform)

            newVal = serialize_transform(transform)

            if len(newVal) < len(val):
                if len(newVal):
                    element.setAttribute(transformAttr, newVal)
                else:
                    element.removeAttribute(transformAttr)
                num += len(val) - len(newVal)

    for child in element.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            num += optimize_transforms(child, options)

    return num
