"""Small recursive descent parser for SVG transform="" data.

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
from decimal import Decimal
from functools import partial
from typing import Any, Generator


class _EOF:
    """Sentinel for end of input."""

    def __repr__(self) -> str:
        return "EOF"


EOF = _EOF()

Token = tuple[str | _EOF, str | None]

lexicon: list[tuple[str, str]] = [
    ("float", r"[-+]?(?:(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.?))(?:[Ee][-+]?[0-9]+)?"),
    ("int", r"[-+]?[0-9]+"),
    ("command", r"(?:matrix|translate|scale|rotate|skew[XY])"),
    ("coordstart", r"\("),
    ("coordend", r"\)"),
]


class Lexer:
    """Break SVG transform data into tokens."""

    def __init__(self, lexicon: list[tuple[str, str]]) -> None:
        self.lexicon = lexicon
        parts = []
        for name, regex in lexicon:
            parts.append("(?P<%s>%s)" % (name, regex))
        self.regex_string = "|".join(parts)
        self.regex = re.compile(self.regex_string)

    def lex(self, text: str) -> Generator[Token, None, None]:
        """Yield (token_type, str_data) tokens."""
        for match in self.regex.finditer(text):
            for name, _ in self.lexicon:
                m = match.group(name)
                if m is not None:
                    yield (name, m)
                    break
        yield (EOF, None)


svg_lexer = Lexer(lexicon)


class SVGTransformationParser:
    """Parse SVG transform="" data into a list of commands.

    Each distinct command will take the form of a tuple (type, data). The
    ``type`` is the character string that defines the type of transformation,
    so either of "translate", "rotate", "scale", "matrix", "skewX" and "skewY".

    The main method is ``parse(text)``.
    """

    def __init__(self, lexer: Lexer = svg_lexer) -> None:
        self.lexer = lexer

        self.command_dispatch: dict[str, Any] = {
            "translate": self.rule_1or2numbers,
            "scale": self.rule_1or2numbers,
            "skewX": self.rule_1number,
            "skewY": self.rule_1number,
            "rotate": self.rule_1or3numbers,
            "matrix": self.rule_6numbers,
        }

        self.number_tokens = list(["int", "float"])

    def parse(self, text: str) -> list[tuple[str, list[Decimal]]]:
        """Parse a string of SVG transform="" data."""
        gen = self.lexer.lex(text)
        next_val_fn = partial(next, *(gen,))

        commands = []
        token = next_val_fn()
        while token[0] is not EOF:
            command, token = self.rule_svg_transform(next_val_fn, token)
            commands.append(command)
        return commands

    def rule_svg_transform(self, next_val_fn, token):
        if token[0] != "command":
            raise SyntaxError("expecting a transformation type; got %r" % (token,))
        command = token[1]
        rule = self.command_dispatch[command]
        token = next_val_fn()
        if token[0] != "coordstart":
            raise SyntaxError("expecting '('; got %r" % (token,))
        numbers, token = rule(next_val_fn, token)
        if token[0] != "coordend":
            raise SyntaxError("expecting ')'; got %r" % (token,))
        token = next_val_fn()
        return (command, numbers), token

    def rule_1or2numbers(self, next_val_fn, token):
        numbers = []
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers.append(number)
        number, token = self.rule_optional_number(next_val_fn, token)
        if number is not None:
            numbers.append(number)
        return numbers, token

    def rule_1number(self, next_val_fn, token):
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers = [number]
        return numbers, token

    def rule_1or3numbers(self, next_val_fn, token):
        numbers = []
        token = next_val_fn()
        number, token = self.rule_number(next_val_fn, token)
        numbers.append(number)
        number, token = self.rule_optional_number(next_val_fn, token)
        if number is not None:
            numbers.append(number)
            number, token = self.rule_number(next_val_fn, token)
            numbers.append(number)
        return numbers, token

    def rule_6numbers(self, next_val_fn, token):
        numbers = []
        token = next_val_fn()
        for _i in range(6):
            number, token = self.rule_number(next_val_fn, token)
            numbers.append(number)
        return numbers, token

    def rule_number(self, next_val_fn, token):
        if token[0] not in self.number_tokens:
            raise SyntaxError("expecting a number; got %r" % (token,))
        x = Decimal(token[1]) * 1
        token = next_val_fn()
        return x, token

    def rule_optional_number(self, next_val_fn, token):
        if token[0] not in self.number_tokens:
            return None, token
        else:
            x = Decimal(token[1]) * 1
            token = next_val_fn()
            return x, token


svg_transform_parser = SVGTransformationParser()
