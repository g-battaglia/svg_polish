"""Optimisation passes for ``<path>`` ``d`` attributes and ``<polygon>``/``<polyline>`` ``points`` lists.

The largest pass in the library — the path optimiser does eight phases
of simplification on a parsed command list before emitting the result.
Each phase is a self-contained transformation; later phases assume
earlier ones have run (for example, the shorthand-command pass relies
on the absolute→relative conversion having already happened).

Public surface:

* :func:`clean_path` — walk a single ``<path>`` element, parse its
  ``d``, run the eight-phase pipeline, and write the result back when
  it is strictly shorter.
* :func:`clean_polygon` — strip the redundant closing point from a
  ``<polygon>`` whose first and last vertex coincide, and re-serialise
  the ``points`` list with scoured precision.
* :func:`clean_polyline` — re-serialise ``<polyline>`` ``points`` with
  scoured precision (no vertex removal — polyline does not auto-close).
* :func:`serialize_path` / :func:`scour_coordinates` — building blocks
  used by :func:`clean_path` and re-used by anything that needs to
  emit a path-like coordinate list.
* :func:`parse_list_of_points` / :func:`control_points` / :func:`flags`
  — parsers and per-command metadata helpers used by the above.
* :func:`is_same_sign` / :func:`is_same_direction` — numeric predicates
  used by the same-direction collapse phase. Module-private in spirit
  but exported for tests.

The module sits below :mod:`svg_polish.passes.length` (it borrows
:func:`scour_unitless_length` for numeric serialisation), but does not
depend on transform / colour / group / gradient passes.
"""

from __future__ import annotations

import optparse
from decimal import Decimal, InvalidOperation, getcontext
from xml.dom.minidom import Element

from svg_polish.constants import RE_COMMA_WSP
from svg_polish.passes.length import scour_unitless_length
from svg_polish.stats import ScourStats
from svg_polish.style import _get_style
from svg_polish.svg_regex import svg_parser
from svg_polish.types import PathData, _precision

__all__ = [
    "clean_path",
    "clean_polygon",
    "clean_polyline",
    "control_points",
    "flags",
    "is_same_direction",
    "is_same_sign",
    "parse_list_of_points",
    "scour_coordinates",
    "serialize_path",
]


def is_same_sign(a: Decimal, b: Decimal) -> bool:
    """Return True if *a* and *b* are both non-negative or both non-positive."""
    return (a <= 0 and b <= 0) or (a >= 0 and b >= 0)


def is_same_direction(x1: Decimal, y1: Decimal, x2: Decimal, y2: Decimal) -> bool:
    """Return True if vectors (x1,y1) and (x2,y2) point in the same direction within scouring precision."""
    if not (is_same_sign(x1, x2) and is_same_sign(y1, y2)):
        return False
    diff = y1 / x1 - y2 / x2
    # ``Context.plus`` rejects ``float``; convert when running under the
    # opt-in float engine.
    one_plus_diff = 1 + diff
    if not isinstance(one_plus_diff, Decimal):
        one_plus_diff = Decimal(str(one_plus_diff))
    return _precision.ctx.plus(one_plus_diff) == 1


def clean_path(element: Element, options: optparse.Values, stats: ScourStats) -> None:
    """Optimize the ``d`` attribute of a ``<path>`` element in-place.

    Runs a multi-phase optimization pipeline on the path data string.
    All coordinates are converted to relative form first, then progressively
    simplified.  The result is only applied if it is shorter than the
    original — this acts as a safety net in case an optimization pass
    increases the output size.

    Pipeline phases (in order):

    1. **Parse** — tokenize the ``d`` attribute into a list of
       ``(command, [coordinates])`` tuples via :mod:`svg_regex`.
    2. **Convert absolute → relative** — rewrite every uppercase command
       (``M``, ``L``, ``C``, ``Q``, ``A``, ``H``, ``V``, ``S``, ``T``)
       to its lowercase equivalent, adjusting coordinates relative to the
       current pen position.  ``Z``/``z`` is normalized to ``z``.
       The arc command (``A`` → ``a``) only adjusts the endpoint
       coordinates; radii, rotation, and flags remain unchanged.
    3. **Remove empty segments** — strip zero-length ``l``, ``c``, ``a``,
       ``q``, ``h``, ``v`` segments (O(n) list building).  Remove
       trailing ``z`` after ``m`` when the subpath is empty.  Convert
       ``m 0 0 …`` to ``l …`` when there is no closing ``z``.
       Skipped when the element has ``stroke-linecap: round|square``
       (those caps render visible dots at zero-length segments).
    4. **Collapse same-direction runs** — merge consecutive ``h``/``v``
       values with the same sign (``h100 200`` → ``h300``) and
       consecutive ``l``/``m`` pairs pointing the same direction.
       Skipped when the element has ``marker-mid`` (markers render on
       intermediate nodes).
    5. **Convert straight curves to lines** — detect cubic Bézier
       segments (``c``) whose control points lie on the straight line
       between start and end, and rewrite them as ``l`` segments.
    6. **Collapse consecutive same-type commands** — merge adjacent
       commands of the same type into one (``l 1,2 l 3,4`` → ``l 1,2,3,4``).
       Implicit linetos after moveto (``m x,y dx,dy``) are also merged.
    7. **Shorten to shorthand commands** — convert ``l`` to ``h``/``v``
       when one coordinate is zero; convert ``c`` to ``s`` when the first
       control point is the reflection of the previous one; convert ``q``
       to ``t`` when the quadratic control point is the reflection of
       the previous one.
    8. **Re-serialize** — write the optimized command list back to a
       string via :func:`serialize_path`.  Only applied if the result is
       shorter than the original ``d`` attribute.

    Args:
        element: A ``<path>`` DOM element with a non-empty ``d`` attribute.
        options: Optimizer options (controls precision via ``digits``/``cdigits``).
        stats: Stats collector — incremented for every segment removed
            and every byte saved in path data.
    """

    # this gets the parser object from svg_regex.py
    oldPathStr = element.getAttribute("d")
    path = svg_parser.parse(oldPathStr)
    style = _get_style(element)

    # This determines whether the stroke has round or square linecaps.  If it does, we do not want to collapse empty
    # segments, as they are actually rendered (as circles or squares with diameter/dimension matching the path-width).
    has_round_or_square_linecaps = (
        element.getAttribute("stroke-linecap") in ["round", "square"]
        or "stroke-linecap" in style
        and style["stroke-linecap"] in ["round", "square"]
    )

    # This determines whether the stroke has intermediate markers.  If it does, we do not want to collapse
    # straight segments running in the same direction, as markers are rendered on the intermediate nodes.
    has_intermediate_markers = (
        element.hasAttribute("marker")
        or element.hasAttribute("marker-mid")
        or "marker" in style
        or "marker-mid" in style
    )

    # The first command must be a moveto, and whether it's relative (m)
    # or absolute (M), the first set of coordinates *is* absolute. So
    # the first iteration of the loop below will get x,y and startx,starty.

    # convert absolute coordinates into relative ones.
    # Reuse the data structure 'path', since we're not adding or removing subcommands.
    # Also reuse the coordinate lists since we're not adding or removing any.
    x = y = 0
    for pathIndex in range(len(path)):
        cmd, data = path[pathIndex]  # Changes to cmd don't get through to the data structure
        # adjust abs to rel
        # only the A command has some values that we don't want to adjust (radii, rotation, flags)
        if cmd == "A":
            for i in range(0, len(data), 7):
                data[i + 5] -= x
                data[i + 6] -= y
                x += data[i + 5]
                y += data[i + 6]
            path[pathIndex] = ("a", data)
        elif cmd == "a":
            x += sum(data[5::7])
            y += sum(data[6::7])
        elif cmd == "H":
            for i in range(len(data)):
                data[i] -= x
                x += data[i]
            path[pathIndex] = ("h", data)
        elif cmd == "h":
            x += sum(data)
        elif cmd == "V":
            for i in range(len(data)):
                data[i] -= y
                y += data[i]
            path[pathIndex] = ("v", data)
        elif cmd == "v":
            y += sum(data)
        elif cmd == "M":
            startx, starty = data[0], data[1]
            # If this is a path starter, don't convert its first
            # coordinate to relative; that would just make it (0, 0)
            if pathIndex != 0:
                data[0] -= x
                data[1] -= y

            x, y = startx, starty
            for i in range(2, len(data), 2):
                data[i] -= x
                data[i + 1] -= y
                x += data[i]
                y += data[i + 1]
            path[pathIndex] = ("m", data)
        elif cmd in ["L", "T"]:
            for i in range(0, len(data), 2):
                data[i] -= x
                data[i + 1] -= y
                x += data[i]
                y += data[i + 1]
            path[pathIndex] = (cmd.lower(), data)
        elif cmd in ["m"]:
            if pathIndex == 0:
                # START OF PATH - this is an absolute moveto
                # followed by relative linetos
                startx, starty = data[0], data[1]
                x, y = startx, starty
                coord_start = 2
            else:
                startx = x + data[0]
                starty = y + data[1]
                coord_start = 0
            for i in range(coord_start, len(data), 2):
                x += data[i]
                y += data[i + 1]
        elif cmd in ["l", "t"]:
            x += sum(data[0::2])
            y += sum(data[1::2])
        elif cmd in ["S", "Q"]:
            for i in range(0, len(data), 4):
                data[i] -= x
                data[i + 1] -= y
                data[i + 2] -= x
                data[i + 3] -= y
                x += data[i + 2]
                y += data[i + 3]
            path[pathIndex] = (cmd.lower(), data)
        elif cmd in ["s", "q"]:
            x += sum(data[2::4])
            y += sum(data[3::4])
        elif cmd == "C":
            for i in range(0, len(data), 6):
                data[i] -= x
                data[i + 1] -= y
                data[i + 2] -= x
                data[i + 3] -= y
                data[i + 4] -= x
                data[i + 5] -= y
                x += data[i + 4]
                y += data[i + 5]
            path[pathIndex] = ("c", data)
        elif cmd == "c":
            x += sum(data[4::6])
            y += sum(data[5::6])
        elif cmd in ["z", "Z"]:
            x, y = startx, starty
            path[pathIndex] = ("z", data)

    # remove empty segments and redundant commands
    # Reuse the data structure 'path' and the coordinate lists, even if we're
    # deleting items, because these deletions are relatively cheap.
    if not has_round_or_square_linecaps:
        # remove empty path segments — O(n) list building instead of O(n²) del
        for pathIndex in range(len(path)):
            cmd, data = path[pathIndex]
            if cmd in ["m", "l", "t"]:
                # m: skip first pair (moveto coords), start filtering from index 2
                # l, t: filter from index 0
                start = 2 if cmd == "m" else 0
                newData = data[:start]
                removed = 0
                for j in range(start, len(data), 2):
                    if data[j] == data[j + 1] == 0:
                        removed += 1
                    else:
                        newData.append(data[j])
                        newData.append(data[j + 1])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed
            elif cmd == "c":
                newData = []
                removed = 0
                for j in range(0, len(data), 6):
                    if data[j] == data[j + 1] == data[j + 2] == data[j + 3] == data[j + 4] == data[j + 5] == 0:
                        removed += 1
                    else:
                        newData.extend(data[j : j + 6])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed
            elif cmd == "a":
                newData = []
                removed = 0
                for j in range(0, len(data), 7):
                    if data[j + 5] == data[j + 6] == 0:
                        removed += 1
                    else:
                        newData.extend(data[j : j + 7])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed
            elif cmd == "q":
                newData = []
                removed = 0
                for j in range(0, len(data), 4):
                    if data[j] == data[j + 1] == data[j + 2] == data[j + 3] == 0:
                        removed += 1
                    else:
                        newData.extend(data[j : j + 4])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed
            elif cmd in ["h", "v"]:
                oldLen = len(data)
                path[pathIndex] = (cmd, [coord for coord in data if coord != 0])
                stats.num_path_segments_removed += len(path[pathIndex][1]) - oldLen

        # remove no-op commands
        pathIndex = len(path)
        subpath_needs_anchor = False
        # NB: We can never rewrite the first m/M command (expect if it
        # is the only command)
        while pathIndex > 1:
            pathIndex -= 1
            cmd, data = path[pathIndex]
            if cmd == "z":
                next_cmd, next_data = path[pathIndex - 1]
                if next_cmd == "m" and len(next_data) == 2:
                    # mX Yz -> mX Y

                    # note the len check on next_data as it is not
                    # safe to rewrite "m0 0 1 1z" in general (it is a
                    # question of where the "pen" ends - you can
                    # continue a draw on the same subpath after a
                    # "z").
                    del path[pathIndex]
                    stats.num_path_segments_removed += 1
                else:
                    # it is not safe to rewrite "m0 0 ..." to "l..."
                    # because of this "z" command.
                    subpath_needs_anchor = True
            elif cmd == "m":
                if len(path) - 1 == pathIndex and len(data) == 2:
                    # Ends with an empty move (but no line/draw
                    # following it)
                    del path[pathIndex]
                    stats.num_path_segments_removed += 1
                    continue
                if subpath_needs_anchor:
                    subpath_needs_anchor = False
                elif data[0] == data[1] == 0:
                    # unanchored, i.e. we can replace "m0 0 ..." with
                    # "l..." as there is no "z" after it.
                    path[pathIndex] = ("l", data[2:])
                    stats.num_path_segments_removed += 1

    # fixup: Delete subcommands having no coordinates.
    path = [elem for elem in path if len(elem[1]) > 0 or elem[0] == "z"]

    # convert straight curves into lines
    newPath = [path[0]]
    for cmd, data in path[1:]:
        i = 0
        newData = data
        if cmd == "c":
            newData = []
            while i < len(data):
                # since all commands are now relative, we can think of previous point as (0,0)
                # and new point (dx,dy) is (data[i+4],data[i+5])
                # eqn of line will be y = (dy/dx)*x or if dx=0 then eqn of line is x=0
                (p1x, p1y) = (data[i], data[i + 1])
                (p2x, p2y) = (data[i + 2], data[i + 3])
                dx = data[i + 4]
                dy = data[i + 5]

                foundStraightCurve = False

                if dx == 0:
                    if p1x == 0 and p2x == 0:
                        foundStraightCurve = True
                else:
                    m = dy / dx
                    if p1y == m * p1x and p2y == m * p2x:
                        foundStraightCurve = True

                if foundStraightCurve:
                    # flush any existing curve coords first
                    if newData:
                        newPath.append((cmd, newData))
                        newData = []
                    # now create a straight line segment
                    newPath.append(("l", [dx, dy]))
                else:
                    newData.extend(data[i : i + 6])

                i += 6
        if newData or cmd == "z" or cmd == "Z":
            newPath.append((cmd, newData))
    path = newPath

    # collapse all consecutive commands of the same type into one command
    prevCmd = ""
    prevData = []
    newPath = []
    for cmd, data in path:
        if prevCmd == "":
            # initialize with current path cmd and data
            prevCmd = cmd
            prevData = data
        else:
            # collapse if
            # - cmd is not moveto (explicit moveto commands are not drawn)
            # - the previous and current commands are the same type,
            # - the previous command is moveto and the current is lineto
            #   (subsequent moveto pairs are treated as implicit lineto commands)
            if cmd != "m" and (cmd == prevCmd or (cmd == "l" and prevCmd == "m")):
                prevData.extend(data)
            # else flush the previous command if it is not the same type as the current command
            else:
                newPath.append((prevCmd, prevData))
                prevCmd = cmd
                prevData = data
    # flush last command and data
    newPath.append((prevCmd, prevData))
    path = newPath

    # convert to shorthand path segments where possible
    newPath = []
    for cmd, data in path:
        # convert line segments into h,v where possible
        if cmd == "l":
            i = 0
            lineTuples: list[tuple[str, list[Decimal]]] = []
            while i < len(data):
                if data[i] == 0:
                    # vertical
                    if lineTuples:
                        # flush the existing line command
                        newPath.append(("l", lineTuples))
                        lineTuples = []
                    # append the v and then the remaining line coords
                    newPath.append(("v", [data[i + 1]]))
                    stats.num_path_segments_removed += 1
                elif data[i + 1] == 0:
                    if lineTuples:
                        # flush the line command, then append the h and then the remaining line coords
                        newPath.append(("l", lineTuples))
                        lineTuples = []
                    newPath.append(("h", [data[i]]))
                    stats.num_path_segments_removed += 1
                else:
                    lineTuples.extend(data[i : i + 2])
                i += 2
            if lineTuples:
                newPath.append(("l", lineTuples))
        # also handle implied relative linetos
        elif cmd == "m":
            i = 2
            lineTuples = [data[0], data[1]]
            while i < len(data):
                if data[i] == 0:
                    # vertical
                    if lineTuples:
                        # flush the existing m/l command
                        newPath.append((cmd, lineTuples))
                        lineTuples = []
                        cmd = "l"  # dealing with linetos now
                    # append the v and then the remaining line coords
                    newPath.append(("v", [data[i + 1]]))
                    stats.num_path_segments_removed += 1
                elif data[i + 1] == 0:
                    if lineTuples:
                        # flush the m/l command, then append the h and then the remaining line coords
                        newPath.append((cmd, lineTuples))
                        lineTuples = []
                        cmd = "l"  # dealing with linetos now
                    newPath.append(("h", [data[i]]))
                    stats.num_path_segments_removed += 1
                else:
                    lineTuples.extend(data[i : i + 2])
                i += 2
            if lineTuples:
                newPath.append((cmd, lineTuples))
        # convert Bézier curve segments into s where possible
        elif cmd == "c":
            # set up the assumed bezier control point as the current point,
            # i.e. (0,0) since we're using relative coords
            bez_ctl_pt = (0, 0)
            # however if the previous command was 's'
            # the assumed control point is a reflection of the previous control point at the current point
            if len(newPath):
                (prevCmd, prevData) = newPath[-1]
                if prevCmd == "s":
                    bez_ctl_pt = (prevData[-2] - prevData[-4], prevData[-1] - prevData[-3])
            i = 0
            curveTuples: list[tuple[str, list[Decimal]]] = []
            while i < len(data):
                # rotate by 180deg means negate both coordinates
                # if the previous control point is equal then we can substitute a
                # shorthand bezier command
                if bez_ctl_pt[0] == data[i] and bez_ctl_pt[1] == data[i + 1]:
                    if curveTuples:
                        newPath.append(("c", curveTuples))
                        curveTuples = []
                    # append the s command
                    newPath.append(("s", [data[i + 2], data[i + 3], data[i + 4], data[i + 5]]))
                    stats.num_path_segments_removed += 1
                else:
                    j = 0
                    while j <= 5:
                        curveTuples.append(data[i + j])
                        j += 1

                # set up control point for next curve segment
                bez_ctl_pt = (data[i + 4] - data[i + 2], data[i + 5] - data[i + 3])
                i += 6

            if curveTuples:
                newPath.append(("c", curveTuples))
        # convert quadratic curve segments into t where possible
        elif cmd == "q":
            quad_ctl_pt = (0, 0)
            i = 0
            curveTuples = []
            while i < len(data):
                if quad_ctl_pt[0] == data[i] and quad_ctl_pt[1] == data[i + 1]:
                    if curveTuples:
                        newPath.append(("q", curveTuples))
                        curveTuples = []
                    # append the t command
                    newPath.append(("t", [data[i + 2], data[i + 3]]))
                    stats.num_path_segments_removed += 1
                else:
                    j = 0
                    while j <= 3:
                        curveTuples.append(data[i + j])
                        j += 1

                quad_ctl_pt = (data[i + 2] - data[i], data[i + 3] - data[i + 1])
                i += 4

            if curveTuples:
                newPath.append(("q", curveTuples))
        else:
            newPath.append((cmd, data))
    path = newPath

    # For each m, l, h or v, collapse unnecessary coordinates that run in the same direction
    # i.e. "h-100-100" becomes "h-200" but "h300-100" does not change.
    # If the path has intermediate markers we have to preserve intermediate nodes, though.
    # Reuse the data structure 'path', since we're not adding or removing subcommands.
    # Also reuse the coordinate lists, even if we're deleting items, because these
    # deletions are relatively cheap.
    # Collapse consecutive coordinates running in same direction — O(n) list building
    if not has_intermediate_markers:
        for pathIndex in range(len(path)):
            cmd, data = path[pathIndex]

            # h / v: collapse same-sign consecutive values
            if cmd in ["h", "v"] and len(data) >= 2:
                newData = [data[0]]
                removed = 0
                for j in range(1, len(data)):
                    if is_same_sign(newData[-1], data[j]):
                        newData[-1] += data[j]
                        removed += 1
                    else:
                        newData.append(data[j])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed

            # l: collapse same-direction consecutive pairs
            elif cmd == "l" and len(data) >= 4:
                newData = [data[0], data[1]]
                removed = 0
                for j in range(2, len(data), 2):
                    if is_same_direction(newData[-2], newData[-1], data[j], data[j + 1]):
                        newData[-2] += data[j]
                        newData[-1] += data[j + 1]
                        removed += 1
                    else:
                        newData.append(data[j])
                        newData.append(data[j + 1])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed

            # m: skip first pair (moveto), collapse rest
            elif cmd == "m" and len(data) >= 6:
                newData = [data[0], data[1], data[2], data[3]]
                removed = 0
                for j in range(4, len(data), 2):
                    if is_same_direction(newData[-2], newData[-1], data[j], data[j + 1]):
                        newData[-2] += data[j]
                        newData[-1] += data[j + 1]
                        removed += 1
                    else:
                        newData.append(data[j])
                        newData.append(data[j + 1])
                if removed:
                    data[:] = newData
                    stats.num_path_segments_removed += removed

    # it is possible that we have consecutive h, v, c, t commands now
    # so again collapse all consecutive commands of the same type into one command
    prevCmd = ""
    prevData = []
    newPath = [path[0]]
    for cmd, data in path[1:]:
        # flush the previous command if it is not the same type as the current command
        if prevCmd and (cmd != prevCmd or cmd == "m"):
            newPath.append((prevCmd, prevData))
            prevCmd = ""
            prevData = []

        # if the previous and current commands are the same type, collapse
        if cmd == prevCmd and cmd != "m":
            prevData.extend(data)

        # save last command and data
        else:
            prevCmd = cmd
            prevData = data
    # flush last command and data
    if prevCmd:
        newPath.append((prevCmd, prevData))
    path = newPath

    newPathStr = serialize_path(path, options)

    # if for whatever reason we actually made the path longer don't use it
    # TODO: maybe we could compare path lengths after each optimization step and use the shortest
    if len(newPathStr) <= len(oldPathStr):
        stats.num_bytes_saved_in_path_data += len(oldPathStr) - len(newPathStr)
        element.setAttribute("d", newPathStr)


def parse_list_of_points(s: str) -> list[Decimal]:
    """Parse a space/comma-separated point list into a flat list of ``Decimal`` coordinates."""
    i = 0

    # (wsp)? comma-or-wsp-separated coordinate pairs (wsp)?
    # coordinate-pair = coordinate comma-or-wsp coordinate
    # coordinate = sign? integer
    # comma-wsp: (wsp+ comma? wsp*) | (comma wsp*)
    ws_nums = RE_COMMA_WSP.split(s.strip())
    nums: list[str | Decimal] = []

    # also, if 100-100 is found, split it into two also
    #  <polygon points="100,-100,100-100,100-100-100,-100-100" />
    for i in range(len(ws_nums)):
        negcoords = ws_nums[i].split("-")

        # this string didn't have any negative coordinates
        if len(negcoords) == 1:
            nums.append(negcoords[0])
        # we got negative coords
        else:
            for j in range(len(negcoords)):
                # first number could be positive
                if j == 0:
                    if negcoords[0]:
                        nums.append(negcoords[0])
                # otherwise all other strings will be negative
                else:
                    # unless we accidentally split a number that was in scientific notation
                    # and had a negative exponent (500.00e-1)
                    prev: str | Decimal = ""
                    if len(nums):
                        prev = nums[len(nums) - 1]
                    if isinstance(prev, str) and prev and prev[len(prev) - 1] in ["e", "E"]:
                        nums[len(nums) - 1] = prev + "-" + negcoords[j]
                    else:
                        nums.append("-" + negcoords[j])

    # if we have an odd number of points, return empty
    if len(nums) % 2 != 0:
        return []

    # now resolve into Decimal values
    i = 0
    while i < len(nums):
        try:
            nums[i] = getcontext().create_decimal(nums[i])
            nums[i + 1] = getcontext().create_decimal(nums[i + 1])
        except InvalidOperation:  # one of the lengths had a unit or is an invalid number
            return []

        i += 2

    return [n for n in nums if isinstance(n, Decimal)]


def clean_polygon(elem: Element, options: optparse.Values) -> int:
    """Remove the redundant closing point from a ``<polygon>`` if it duplicates the first."""
    num_points_removed_from_polygon = 0

    pts = parse_list_of_points(elem.getAttribute("points"))
    N = len(pts) / 2
    if N >= 2:
        (startx, starty) = pts[:2]
        (endx, endy) = pts[-2:]
        if startx == endx and starty == endy:
            del pts[-2:]
            num_points_removed_from_polygon += 1
    elem.setAttribute("points", scour_coordinates(pts, options, True))
    return num_points_removed_from_polygon


def clean_polyline(elem: Element, options: optparse.Values) -> None:
    """
    Scour the polyline points attribute
    """
    pts = parse_list_of_points(elem.getAttribute("points"))
    elem.setAttribute("points", scour_coordinates(pts, options, True))


def control_points(cmd: str, data: list[Decimal]) -> list[int]:
    """Return indices of control-point values in *data* for path command *cmd*."""
    cmd = cmd.lower()
    if cmd in ["c", "s", "q"]:
        indices = range(len(data))
        if cmd == "c":  # c: (x1 y1 x2 y2 x y)+
            return [index for index in indices if (index % 6) < 4]
        elif cmd in ["s", "q"]:  # s: (x2 y2 x y)+   q: (x1 y1 x y)+
            return [index for index in indices if (index % 4) < 2]

    return []


def flags(cmd: str, data: list[Decimal]) -> list[int]:
    """Return indices of arc-flag values in *data* for path command *cmd*."""
    if cmd.lower() == "a":  # a: (rx ry x-axis-rotation large-arc-flag sweep-flag x y)+
        indices = range(len(data))
        return [index for index in indices if (index % 7) in [3, 4]]

    return []


def serialize_path(pathObj: PathData, options: optparse.Values) -> str:
    """Serialize optimized path data back to a ``d`` attribute string.

    Pre-allocates a list with ``2 * len(pathObj)`` slots and appends the command
    and its coordinates separately. This avoids the per-iteration intermediate
    ``cmd + scour_coordinates(...)`` concatenation that the previous generator
    form created.
    """
    # elliptical arc commands must have comma/wsp separating the coordinates
    # this fixes an issue outlined in Fix https://bugs.launchpad.net/scour/+bug/412754
    parts: list[str] = []
    for cmd, data in pathObj:
        parts.append(cmd)
        parts.append(scour_coordinates(data, options, control_points=control_points(cmd, data), flags=flags(cmd, data)))
    return "".join(parts)


def scour_coordinates(
    data: list[Decimal],
    options: optparse.Values,
    force_whitespace: bool = False,
    control_points: list[int] | None = None,
    flags: list[int] | None = None,
) -> str:
    """Serialize coordinate data with minimal whitespace and reduced precision."""
    control_points = control_points or []
    flags = flags or []
    if data is not None:
        newData: list[str] = []
        previousCoord = ""
        for c, coord in enumerate(data):
            is_control_point = c in control_points
            scouredCoord = scour_unitless_length(
                coord, renderer_workaround=options.renderer_workaround, is_control_point=is_control_point
            )
            # don't output a space if this number starts with a dot (.) or minus sign (-); we only need a space if
            #   - this number starts with a digit
            #   - this number starts with a dot but the previous number had *no* dot or exponent
            #     i.e. '1.3 0.5' -> '1.3.5' or '1e3 0.5' -> '1e3.5' is fine but '123 0.5' -> '123.5' is obviously not
            #   - 'force_whitespace' is explicitly set to 'True'
            # we never need a space after flags (occurring in elliptical arcs), but librsvg struggles without it
            if (
                c > 0
                and (
                    force_whitespace
                    or scouredCoord[0].isdigit()
                    or (scouredCoord[0] == "." and not ("." in previousCoord or "e" in previousCoord))
                )
                and ((c - 1 not in flags) or options.renderer_workaround)
            ):
                newData.append(" ")

            # add the scoured coordinate to the path string
            newData.append(scouredCoord)
            previousCoord = scouredCoord

        # What we need to do to work around GNOME bugs 548494, 563933 and 620565, is to make sure that a dot doesn't
        # immediately follow a command  (so 'h50' and 'h0.5' are allowed, but not 'h.5').
        # Then, we need to add a space character after any coordinates  having an 'e' (scientific notation),
        # so as to have the exponent separate from the next number.
        # TODO: Check whether this is still required (bugs all marked as fixed, might be time to phase it out)
        if options.renderer_workaround:
            if len(newData) > 0:
                for i in range(1, len(newData)):
                    if newData[i][0] == "-" and "e" in newData[i - 1]:
                        newData[i - 1] += " "
                return "".join(newData)
        else:
            return "".join(newData)

    return ""
