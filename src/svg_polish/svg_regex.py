# This software is OSI Certified Open Source Software.
# OSI Certified is a certification mark of the Open Source Initiative.
#
# Copyright (c) 2006, Enthought, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#  * Neither the name of Enthought, Inc. nor the names of its contributors may
#    be used to endorse or promote products derived from this software without
#    specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Small hand-written recursive descent parser for SVG ``<path>`` *d* data.

This module implements a two-stage pipeline for parsing SVG path data strings
(as defined in SVG 1.1 spec section 8.3) into structured command lists:

1. **Lexer** (:class:`Lexer`) — Tokenises the raw path string into a stream of
   ``(token_type, text_value)`` pairs.  Token types are ``"command"`` (single
   letter A–Z / a–z), ``"float"``, and ``"int"``.  The lexer appends a
   sentinel ``(EOF, None)`` to signal end-of-input.

2. **Parser** (:class:`SVGPathParser`) — Consumes the token stream via
   recursive-descent rules, one rule per SVG path command type.  Each rule
   collects the required numeric arguments and returns a ``(command_letter,
   data_list)`` tuple.  The parser enforces the SVG grammar: wrong argument
   counts, missing numbers, or negative radii raise :class:`SyntaxError`.

Supported SVG path commands (SVG 1.1 §8.3.2):

    ============  ====================  ========
    Letter        Meaning               Args
    ============  ====================  ========
    M / m         moveto                (x y)+
    L / l         lineto                (x y)+
    H / h         horizontal lineto     x+
    V / v         vertical lineto       y+
    C / c         curveto (cubic)       (x1 y1 x2 y2 x y)+
    S / s         smooth curveto        (x2 y2 x y)+
    Q / q         quadratic curveto     (x1 y1 x y)+
    T / t         smooth quadratic      (x y)+
    A / a         elliptical arc        (rx ry θ flag flag x y)+
    Z / z         closepath             —
    ============  ====================  ========

The module exposes a pre-built singleton parser:

    ``svg_parser`` — an :class:`SVGPathParser` ready for use.

Examples::

    >>> from svg_polish.svg_regex import svg_parser
    >>> svg_parser.parse('M 10,20 30,40V50 60 70')
    [('M', [...]), ('V', [...])]

    >>> svg_parser.parse('M 0.6051.5')  # An edge case: two numbers sharing a dot
    [('M', [...])]

    >>> svg_parser.parse('M 100-200')  # Negative sign delimits two numbers
    [('M', [...])]

All numeric values are returned as :class:`decimal.Decimal` for lossless
precision — this avoids floating-point rounding that could alter path geometry
during optimization.

Original copyright:
    Copyright (c) 2006, Enthought, Inc.
    BSD-style license (see header above).
"""

from __future__ import annotations

import re
from decimal import Decimal, getcontext
from functools import partial
from typing import Any, Generator


class _EOF:
    """Sentinel for end of input."""

    def __repr__(self) -> str:
        return "EOF"


EOF = _EOF()

Token = tuple[str | _EOF, str | None]

# Lexer token definitions: each entry is (type_name, regex_pattern).
# Order matters — "float" is listed before "int" so that e.g. "3.14"
# is matched as a float, not as int "3" followed by stray ".14".
lexicon: list[tuple[str, str]] = [
    ("float", r"[-+]?(?:(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.?))(?:[Ee][-+]?[0-9]+)?"),
    ("int", r"[-+]?[0-9]+"),
    ("command", r"[AaCcHhLlMmQqSsTtVvZz]"),
]


class Lexer:
    """Break SVG path data into tokens.

    The SVG spec requires that tokens are greedy. This lexer relies on Python's
    regexes defaulting to greediness.

    The combined regex is built from the *lexicon* at construction time and
    applied via :meth:`finditer` — each match yields exactly one token.
    """

    def __init__(self, lexicon: list[tuple[str, str]]) -> None:
        self.lexicon = lexicon
        # Build a single combined regex with named groups: (?P<float>...)|(?P<int>...)|…
        parts = []
        for name, regex in lexicon:
            parts.append("(?P<%s>%s)" % (name, regex))
        self.regex_string = "|".join(parts)
        self.regex = re.compile(self.regex_string)

    def lex(self, text: str) -> Generator[Token, None, None]:
        """Yield ``(token_type, str_data)`` tokens from *text*.

        Iterates over all non-overlapping regex matches, yielding one token
        per match.  After all matches are exhausted, yields a final
        ``(EOF, None)`` sentinel so the parser can detect end-of-input
        without catching ``StopIteration``.
        """
        for match in self.regex.finditer(text):
            for name, _ in self.lexicon:
                m = match.group(name)
                if m is not None:
                    yield (name, m)
                    break
        yield (EOF, None)


# Pre-built lexer instance using the SVG path lexicon defined above.
svg_lexer = Lexer(lexicon)


class SVGPathParser:
    """Parse SVG ``<path>`` *d* attribute data into a list of commands.

    Each distinct command will take the form of a tuple ``(command, data)``. The
    ``command`` is just the character string that starts the command group in the
    ``<path>`` data, so ``'M'`` for absolute moveto, ``'m'`` for relative moveto,
    ``'Z'`` for closepath, etc.

    The ``data`` list contains :class:`~decimal.Decimal` values.  The number of
    values depends on the command type:

    * **moveto / lineto** (M, m, L, l): pairs of ``(x, y)``.
    * **orthogonal lineto** (H, h, V, v): single coordinates.
    * **cubic Bézier** (C, c): three pairs ``(x1, y1, x2, y2, x, y)``.
    * **smooth cubic** (S, s): two pairs ``(x2, y2, x, y)``.
    * **quadratic Bézier** (Q, q): two pairs ``(x1, y1, x, y)``.
    * **smooth quadratic** (T, t): one pair ``(x, y)``.
    * **elliptical arc** (A, a): seven values ``(rx, ry, rotation, large_arc, sweep, x, y)``.
    * **closepath** (Z, z): empty list ``[]``.

    The main entry point is :meth:`parse`.
    """

    def __init__(self, lexer: Lexer = svg_lexer) -> None:
        self.lexer = lexer

        # Dispatch table: maps each command letter to the parsing rule that
        # knows how many numeric arguments to consume.
        self.command_dispatch: dict[str, Any] = {
            "Z": self.rule_closepath,
            "z": self.rule_closepath,
            "M": self.rule_moveto_or_lineto,
            "m": self.rule_moveto_or_lineto,
            "L": self.rule_moveto_or_lineto,
            "l": self.rule_moveto_or_lineto,
            "H": self.rule_orthogonal_lineto,
            "h": self.rule_orthogonal_lineto,
            "V": self.rule_orthogonal_lineto,
            "v": self.rule_orthogonal_lineto,
            "C": self.rule_curveto3,
            "c": self.rule_curveto3,
            "S": self.rule_curveto2,
            "s": self.rule_curveto2,
            "Q": self.rule_curveto2,
            "q": self.rule_curveto2,
            "T": self.rule_curveto1,
            "t": self.rule_curveto1,
            "A": self.rule_elliptical_arc,
            "a": self.rule_elliptical_arc,
        }

        # Token types that represent numeric values (used for argument parsing).
        self.number_tokens = list(["int", "float"])

    def parse(self, text: str) -> list[tuple[str, list[Any]]]:
        """Parse a string of SVG ``<path>`` data into a command list.

        This is the main entry point.  It tokenises *text* via the lexer,
        then delegates to :meth:`rule_svg_path` which drives the
        recursive-descent parse.

        Args:
            text: Raw path data string, e.g. ``"M 10 20 L 30 40"``.

        Returns:
            A list of ``(command_letter, data)`` tuples.

        Raises:
            SyntaxError: If the input does not conform to the SVG path grammar.
        """
        gen = self.lexer.lex(text)
        next_val_fn = partial(next, *(gen,))
        token = next_val_fn()
        return self.rule_svg_path(next_val_fn, token)

    def rule_svg_path(self, next_val_fn, token):
        """Top-level rule: consume command groups until EOF."""
        commands = []
        while token[0] is not EOF:
            if token[0] != "command":
                raise SyntaxError("expecting a command; got %r" % (token,))
            rule = self.command_dispatch[token[1]]
            command_group, token = rule(next_val_fn, token)
            commands.append(command_group)
        return commands

    def rule_closepath(self, next_val_fn, token):
        """Z / z: close the current subpath.  No numeric arguments."""
        command = token[1]
        token = next_val_fn()
        return (command, []), token

    def rule_moveto_or_lineto(self, next_val_fn, token):
        """M / m / L / l: consume one or more ``(x, y)`` coordinate pairs."""
        command = token[1]
        token = next_val_fn()
        coordinates = []
        while token[0] in self.number_tokens:
            pair, token = self.rule_coordinate_pair(next_val_fn, token)
            coordinates.extend(pair)
        return (command, coordinates), token

    def rule_orthogonal_lineto(self, next_val_fn, token):
        """H / h / V / v: consume one or more single coordinate values."""
        command = token[1]
        token = next_val_fn()
        coordinates = []
        while token[0] in self.number_tokens:
            coord, token = self.rule_coordinate(next_val_fn, token)
            coordinates.append(coord)
        return (command, coordinates), token

    def rule_curveto3(self, next_val_fn, token):
        """C / c: consume one or more cubic Bézier triplets (3 coordinate pairs each)."""
        command = token[1]
        token = next_val_fn()
        coordinates = []
        while token[0] in self.number_tokens:
            pair1, token = self.rule_coordinate_pair(next_val_fn, token)
            pair2, token = self.rule_coordinate_pair(next_val_fn, token)
            pair3, token = self.rule_coordinate_pair(next_val_fn, token)
            coordinates.extend(pair1)
            coordinates.extend(pair2)
            coordinates.extend(pair3)
        return (command, coordinates), token

    def rule_curveto2(self, next_val_fn, token):
        """S / s / Q / q: consume one or more smooth/quadratic pairs (2 coordinate pairs each)."""
        command = token[1]
        token = next_val_fn()
        coordinates = []
        while token[0] in self.number_tokens:
            pair1, token = self.rule_coordinate_pair(next_val_fn, token)
            pair2, token = self.rule_coordinate_pair(next_val_fn, token)
            coordinates.extend(pair1)
            coordinates.extend(pair2)
        return (command, coordinates), token

    def rule_curveto1(self, next_val_fn, token):
        """T / t: consume one or more smooth quadratic coordinate pairs."""
        command = token[1]
        token = next_val_fn()
        coordinates = []
        while token[0] in self.number_tokens:
            pair1, token = self.rule_coordinate_pair(next_val_fn, token)
            coordinates.extend(pair1)
        return (command, coordinates), token

    def rule_elliptical_arc(self, next_val_fn, token):
        """A / a: consume one or more elliptical arc parameter groups.

        Each group consists of 7 values: ``(rx, ry, x-axis-rotation,
        large-arc-flag, sweep-flag, x, y)``.  The ``rx`` and ``ry`` values
        must be non-negative (per SVG spec); a negative value raises
        :class:`SyntaxError`.  The flag values must be ``0`` or ``1``.
        """
        command = token[1]
        token = next_val_fn()
        arguments = []
        while token[0] in self.number_tokens:
            # rx — x-radius (must be >= 0)
            rx = Decimal(token[1]) * 1
            if rx < Decimal("0.0"):
                raise SyntaxError("expecting a nonnegative number; got %r" % (token,))

            # ry — y-radius (must be >= 0)
            token = next_val_fn()
            if token[0] not in self.number_tokens:
                raise SyntaxError("expecting a number; got %r" % (token,))
            ry = Decimal(token[1]) * 1
            if ry < Decimal("0.0"):
                raise SyntaxError("expecting a nonnegative number; got %r" % (token,))

            # x-axis-rotation (decimal degrees)
            token = next_val_fn()
            if token[0] not in self.number_tokens:
                raise SyntaxError("expecting a number; got %r" % (token,))
            axis_rotation = Decimal(token[1]) * 1

            # large-arc-flag (0 or 1).
            # SVG allows flag values to be concatenated without whitespace/delimiter,
            # e.g. "01" means large_arc=0, sweep=1.  Handle that here.
            token = next_val_fn()
            if token[1][0] not in ("0", "1"):
                raise SyntaxError("expecting a boolean flag; got %r" % (token,))
            large_arc_flag = Decimal(token[1][0]) * 1

            if len(token[1]) > 1:
                # Multi-char token: consume only the first character as the flag,
                # leave the rest for the next token.
                token = list(token)
                token[1] = token[1][1:]
            else:
                token = next_val_fn()

            # sweep-flag (0 or 1) — same concatenation logic as large-arc-flag.
            if token[1][0] not in ("0", "1"):
                raise SyntaxError("expecting a boolean flag; got %r" % (token,))
            sweep_flag = Decimal(token[1][0]) * 1

            if len(token[1]) > 1:
                token = list(token)
                token[1] = token[1][1:]
            else:
                token = next_val_fn()

            # (x, y) — endpoint of the arc
            if token[0] not in self.number_tokens:
                raise SyntaxError("expecting a number; got %r" % (token,))
            x = Decimal(token[1]) * 1

            token = next_val_fn()
            if token[0] not in self.number_tokens:
                raise SyntaxError("expecting a number; got %r" % (token,))
            y = Decimal(token[1]) * 1

            token = next_val_fn()
            arguments.extend([rx, ry, axis_rotation, large_arc_flag, sweep_flag, x, y])

        return (command, arguments), token

    def rule_coordinate(self, next_val_fn, token):
        """Consume a single numeric value from the token stream."""
        if token[0] not in self.number_tokens:
            raise SyntaxError("expecting a number; got %r" % (token,))
        # create_decimal() respects the current decimal context for precision.
        x = getcontext().create_decimal(token[1])
        token = next_val_fn()
        return x, token

    def rule_coordinate_pair(self, next_val_fn, token):
        """Consume two consecutive numeric values (x, y) from the token stream."""
        if token[0] not in self.number_tokens:
            raise SyntaxError("expecting a number; got %r" % (token,))
        x = getcontext().create_decimal(token[1])
        token = next_val_fn()
        if token[0] not in self.number_tokens:
            raise SyntaxError("expecting a number; got %r" % (token,))
        y = getcontext().create_decimal(token[1])
        token = next_val_fn()
        return [x, y], token


# Pre-built parser instance — use this for all path parsing.
svg_parser = SVGPathParser()
