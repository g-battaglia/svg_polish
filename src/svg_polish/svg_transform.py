"""Small recursive descent parser for SVG ``transform`` attribute data.

This module implements a two-stage pipeline for parsing SVG transform strings
(as defined in SVG 1.1 spec section 7.6) into structured transform lists:

1. **Lexer** (:class:`Lexer`) — Tokenises the raw transform string into a stream
   of ``(token_type, text_value)`` pairs.  Token types are ``"command"`` (the
   transform function name), ``"coordstart"`` (``(``), ``"coordend"`` (``)``),
   ``"float"``, and ``"int"``.  A trailing ``(EOF, None)`` sentinel marks
   end-of-input.

2. **Parser** (:class:`SVGTransformationParser`) — Consumes the token stream
   and returns a list of ``(transform_type, numbers)`` tuples, one per
   transform function in the input.

Supported SVG transform functions (SVG 1.1 §7.6):

    ==============  =========================  ==============
    Function        Meaning                    Argument count
    ==============  =========================  ==============
    translate(tx)   Translate by tx            1
    translate(tx,ty) Translate by tx, ty       2
    scale(sx)       Scale by sx (sy = sx)      1
    scale(sx, sy)   Scale by sx, sy            2
    rotate(a)       Rotate a degrees           1
    rotate(a, cx, cy) Rotate a deg around (cx, cy)  3
    skewX(a)        Skew along X by a degrees  1
    skewY(a)        Skew along Y by a degrees  1
    matrix(a,b,c,d,e,f)  Full 2×3 affine matrix  6
    ==============  =========================  ==============

The module exposes a pre-built singleton parser:

    ``svg_transform_parser`` — an :class:`SVGTransformationParser` ready for use.

All numeric values are returned as :class:`decimal.Decimal` for lossless
precision — this avoids floating-point rounding that could alter transform
geometry during optimization.

Original copyright:
    Copyright 2010 Louis Simard
    Part of Scour (http://www.codedread.com/scour/)
    Licensed under the Apache License, Version 2.0

Examples::

    >>> from svg_polish.svg_transform import svg_transform_parser
    >>> svg_transform_parser.parse('translate(50, 50)')
    [('translate', [Decimal('50'), Decimal('50')])]
    >>> svg_transform_parser.parse('rotate(36 50,50)')
    [('rotate', [Decimal('36'), Decimal('50'), Decimal('50')])]
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal
from functools import partial
from typing import Any, Generator, cast

from svg_polish.types import _precision


def _make_number(text: str) -> Decimal:
    """Parse *text* into a numeric value sized for the current engine.

    Mirrors :func:`svg_polish.svg_regex._make_number`: returns a
    normalised :class:`~decimal.Decimal` under the default engine and a
    native :class:`float` under ``decimal_engine="float"``. The return
    is cast to ``Decimal`` for the type system; downstream transform
    code uses arithmetic that works on either.
    """
    if _precision.engine == "float":
        return cast(Decimal, float(text))
    return Decimal(text) * 1


class _EOF:
    """Sentinel for end of input."""

    def __repr__(self) -> str:
        """Return ``"EOF"`` so error messages mention end-of-input clearly."""
        return "EOF"


EOF = _EOF()

Token = tuple[str | _EOF, str | None]

# Each parser rule takes a "next token" thunk plus the current token and
# returns the parsed value(s) together with the token that follows it.
NextTokenFn = Callable[[], Token]
TransformTuple = tuple[str, list[Decimal]]
RuleResult = tuple[TransformTuple, Token]
NumbersResult = tuple[list[Decimal], Token]

# Lexer token definitions: each entry is (type_name, regex_pattern).
# "float" is listed before "int" so that e.g. "3.14" is matched as one float
# rather than int "3" followed by stray ".14".
# "command" matches the six SVG transform function names.
lexicon: list[tuple[str, str]] = [
    ("float", r"[-+]?(?:(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.?))(?:[Ee][-+]?[0-9]+)?"),
    ("int", r"[-+]?[0-9]+"),
    ("command", r"(?:matrix|translate|scale|rotate|skew[XY])"),
    ("coordstart", r"\("),
    ("coordend", r"\)"),
]


class Lexer:
    """Break SVG ``transform`` attribute data into tokens.

    The combined regex is built from the *lexicon* at construction time and
    applied via :meth:`finditer` — each match yields exactly one token.
    """

    def __init__(self, lexicon: list[tuple[str, str]]) -> None:
        """Compile *lexicon* into a single combined regex.

        Lexicon order matters (first match wins): floats must precede ints,
        commands must precede ``coordstart``/``coordend``. The lexicon
        defined in this module is the canonical SVG ``transform`` lexicon.

        Args:
            lexicon: Ordered list of ``(token_name, regex_pattern)`` pairs.
        """
        self.lexicon = lexicon
        # Build a single combined regex with named groups: (?P<float>...)|(?P<int>...)|…
        parts = []
        for name, regex in lexicon:
            parts.append("(?P<%s>%s)" % (name, regex))
        self.regex_string = "|".join(parts)
        self.regex = re.compile(self.regex_string)

    def lex(self, text: str) -> Generator[Token, None, None]:
        """Yield ``(token_type, str_data)`` tokens from *text*.

        After all matches are exhausted, yields a final ``(EOF, None)``
        sentinel so the parser can detect end-of-input without catching
        ``StopIteration``.
        """
        for match in self.regex.finditer(text):
            for name, _ in self.lexicon:
                m = match.group(name)
                if m is not None:
                    yield (name, m)
                    break
        yield (EOF, None)


# Pre-built lexer instance using the SVG transform lexicon defined above.
svg_lexer = Lexer(lexicon)


class SVGTransformationParser:
    """Parse SVG ``transform`` attribute data into a list of commands.

    Each distinct command takes the form of a tuple ``(type, data)``. The
    ``type`` is the transform function name: ``"translate"``, ``"rotate"``,
    ``"scale"``, ``"matrix"``, ``"skewX"``, or ``"skewY"``.

    The ``data`` list contains :class:`~decimal.Decimal` values whose count
    depends on the transform type (see module docstring for details).

    The main entry point is :meth:`parse`.
    """

    def __init__(self, lexer: Lexer = svg_lexer) -> None:
        """Wire the parser to a *lexer* and build the transform dispatch table.

        Defaults to :data:`svg_lexer` (the module-level lexer pre-built from
        the SVG transform lexicon). The dispatch table maps each of the six
        SVG transform functions (``translate``, ``scale``, ``rotate``,
        ``skewX``, ``skewY``, ``matrix``) to its argument-arity rule.

        Args:
            lexer: Token producer. Must yield tokens matching the transform
                lexicon and a final ``(EOF, None)`` sentinel.
        """
        self.lexer = lexer

        # Dispatch table: maps each transform type name to the rule that
        # knows how many numeric arguments to expect.
        self.command_dispatch: dict[str, Any] = {
            "translate": self.rule_1or2numbers,
            "scale": self.rule_1or2numbers,
            "skewX": self.rule_1number,
            "skewY": self.rule_1number,
            "rotate": self.rule_1or3numbers,
            "matrix": self.rule_6numbers,
        }

        # Token types that represent numeric values (used for argument parsing).
        self.number_tokens = list(["int", "float"])

    def parse(self, text: str) -> list[tuple[str, list[Decimal]]]:
        """Parse a string of SVG ``transform`` attribute data.

        This is the main entry point.  It tokenises *text* via the lexer,
        then iterates consuming transform commands until EOF.

        Args:
            text: Raw transform string, e.g. ``"translate(10,20) scale(2)"``.

        Returns:
            A list of ``(transform_type, data)`` tuples.

        Raises:
            SyntaxError: If the input does not conform to the SVG transform grammar.
        """
        gen = self.lexer.lex(text)
        next_val_fn = partial(next, *(gen,))

        commands = []
        token = next_val_fn()
        while token[0] is not EOF:
            command, token = self.rule_svg_transform(next_val_fn, token)
            commands.append(command)
        return commands

    def rule_svg_transform(self, next_val_fn: NextTokenFn, token: Token) -> RuleResult:
        """Consume a single transform function: ``type(args)``."""
        if token[0] != "command":
            raise SyntaxError("expecting a transformation type; got %r" % (token,))
        command = token[1]
        assert command is not None
        rule = self.command_dispatch[command]
        token = next_val_fn()
        if token[0] != "coordstart":
            raise SyntaxError("expecting '('; got %r" % (token,))
        numbers, token = rule(next_val_fn, token)
        if token[0] != "coordend":
            raise SyntaxError("expecting ')'; got %r" % (token,))
        token = next_val_fn()
        return (command, numbers), token

    def rule_1or2numbers(self, next_val_fn: NextTokenFn, token: Token) -> NumbersResult:
        """Consume 1 required number and 1 optional number.

        Used by ``translate`` and ``scale`` where the second argument defaults
        to the first if omitted.
        """
        numbers: list[Decimal] = []
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers.append(number)
        opt_number, token = self.rule_optional_number(next_val_fn, token)
        if opt_number is not None:
            numbers.append(opt_number)
        return numbers, token

    def rule_1number(self, next_val_fn: NextTokenFn, token: Token) -> NumbersResult:
        """Consume exactly 1 required number.

        Used by ``skewX`` and ``skewY``.
        """
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers = [number]
        return numbers, token

    def rule_1or3numbers(self, next_val_fn: NextTokenFn, token: Token) -> NumbersResult:
        """Consume 1 required number and optionally 2 more.

        Used by ``rotate``: ``rotate(angle)`` or ``rotate(angle, cx, cy)``.
        If the optional second number is present, a third is required.
        """
        numbers: list[Decimal] = []
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers.append(number)
        opt_number, token = self.rule_optional_number(next_val_fn, token)
        if opt_number is not None:
            numbers.append(opt_number)
            number, token = self.rule_number(next_val_fn, token)
            numbers.append(number)
        return numbers, token

    def rule_6numbers(self, next_val_fn: NextTokenFn, token: Token) -> NumbersResult:
        """Consume exactly 6 required numbers.

        Used by ``matrix(a, b, c, d, e, f)`` representing a 2×3 affine matrix.
        """
        numbers: list[Decimal] = []
        token = next_val_fn()
        for _i in range(6):
            number, token = self.rule_number(next_val_fn, token)
            numbers.append(number)
        return numbers, token

    def rule_number(self, next_val_fn: NextTokenFn, token: Token) -> tuple[Decimal, Token]:
        """Consume a required numeric token. Raises SyntaxError if not a number."""
        if token[0] not in self.number_tokens:
            raise SyntaxError("expecting a number; got %r" % (token,))
        # _make_number switches between Decimal and float per the active engine.
        assert token[1] is not None
        x = _make_number(token[1])
        token = next_val_fn()
        return x, token

    def rule_optional_number(self, next_val_fn: NextTokenFn, token: Token) -> tuple[Decimal | None, Token]:
        """Consume an optional numeric token.

        Returns ``(value, token)`` if a number was found, or ``(None, token)``
        (with token unchanged) if the next token is not a number.
        """
        if token[0] not in self.number_tokens:
            return None, token
        else:
            assert token[1] is not None
            x = _make_number(token[1])
            token = next_val_fn()
            return x, token


# Pre-built parser instance — use this for all transform parsing.
svg_transform_parser = SVGTransformationParser()
