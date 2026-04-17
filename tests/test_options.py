"""Tests for :class:`svg_polish.options.OptimizeOptions` (Sprint 3, M1).

Covers default values, validation of every constraint declared in
``__post_init__``, frozen-dataclass immutability, ``dataclasses.replace``
semantics, and the ``_to_optparse_values`` bridge that feeds the legacy
internal pipeline.
"""

from __future__ import annotations

import dataclasses

import pytest

from svg_polish.exceptions import InvalidOptionError
from svg_polish.options import OptimizeOptions


class TestDefaults:
    """Default values must match the documented secure-by-default policy."""

    def test_secure_defaults(self) -> None:
        opts = OptimizeOptions()
        assert opts.allow_xml_entities is False
        assert opts.max_input_bytes == 100 * 1024 * 1024

    def test_lossless_engine_default(self) -> None:
        opts = OptimizeOptions()
        assert opts.decimal_engine == "decimal"
        assert opts.xml_backend == "minidom"

    def test_precision_defaults(self) -> None:
        opts = OptimizeOptions()
        assert opts.digits == 5
        # cdigits sentinel (-1) must resolve to digits in __post_init__
        assert opts.cdigits == 5

    def test_explicit_cdigits_kept(self) -> None:
        opts = OptimizeOptions(digits=4, cdigits=2)
        assert opts.digits == 4
        assert opts.cdigits == 2

    def test_independent_cdigits_with_default_digits(self) -> None:
        opts = OptimizeOptions(cdigits=3)
        assert opts.digits == 5
        assert opts.cdigits == 3


class TestValidation:
    """Each ``__post_init__`` guard must reject invalid input."""

    @pytest.mark.parametrize("digits", [0, -1, -100])
    def test_digits_must_be_positive(self, digits: int) -> None:
        with pytest.raises(InvalidOptionError, match="digits must be >= 1"):
            OptimizeOptions(digits=digits)

    @pytest.mark.parametrize("cdigits", [0, -2, -100])
    def test_cdigits_must_be_positive(self, cdigits: int) -> None:
        # Negative values other than the -1 sentinel are invalid.
        with pytest.raises(InvalidOptionError, match="cdigits must be >= 1"):
            OptimizeOptions(cdigits=cdigits)

    def test_indent_depth_must_be_non_negative(self) -> None:
        with pytest.raises(InvalidOptionError, match="indent_depth must be >= 0"):
            OptimizeOptions(indent_depth=-1)

    def test_indent_depth_zero_is_valid(self) -> None:
        # Zero indent depth is meaningful (e.g. paired with newlines=False)
        # so it must be accepted, only negative values rejected.
        opts = OptimizeOptions(indent_depth=0)
        assert opts.indent_depth == 0

    def test_invalid_indent_type(self) -> None:
        with pytest.raises(InvalidOptionError, match="invalid indent_type"):
            OptimizeOptions(indent_type="bogus")  # type: ignore[arg-type]

    def test_invalid_decimal_engine(self) -> None:
        with pytest.raises(InvalidOptionError, match="invalid decimal_engine"):
            OptimizeOptions(decimal_engine="rational")  # type: ignore[arg-type]

    def test_invalid_xml_backend(self) -> None:
        with pytest.raises(InvalidOptionError, match="invalid xml_backend"):
            OptimizeOptions(xml_backend="expat")  # type: ignore[arg-type]

    def test_xml_backend_lxml_rejected_in_v1_0(self) -> None:
        # lxml backend is planned for a v1.x release but not wired yet;
        # accepting it silently would mislead users into thinking they have
        # the speedup. Reject loudly until the proxy adapter ships.
        with pytest.raises(InvalidOptionError, match="only 'minidom'"):
            OptimizeOptions(xml_backend="lxml")  # type: ignore[arg-type]

    def test_xml_backend_auto_rejected_in_v1_0(self) -> None:
        with pytest.raises(InvalidOptionError, match="only 'minidom'"):
            OptimizeOptions(xml_backend="auto")  # type: ignore[arg-type]

    def test_max_input_bytes_too_small(self) -> None:
        with pytest.raises(InvalidOptionError, match="max_input_bytes must be >= 1024"):
            OptimizeOptions(max_input_bytes=512)

    def test_max_input_bytes_none_disables_check(self) -> None:
        opts = OptimizeOptions(max_input_bytes=None)
        assert opts.max_input_bytes is None

    def test_max_input_bytes_at_minimum(self) -> None:
        opts = OptimizeOptions(max_input_bytes=1024)
        assert opts.max_input_bytes == 1024

    def test_invalid_option_error_is_value_error(self) -> None:
        # InvalidOptionError must remain a ValueError subclass so that callers
        # who catch ValueError keep working without an svg_polish-specific
        # except clause.
        with pytest.raises(ValueError):
            OptimizeOptions(digits=0)


class TestImmutability:
    """``frozen=True`` must prevent post-construction mutation."""

    def test_cannot_assign_after_construction(self) -> None:
        opts = OptimizeOptions()
        with pytest.raises(dataclasses.FrozenInstanceError):
            opts.digits = 9  # type: ignore[misc]

    def test_replace_returns_new_instance(self) -> None:
        original = OptimizeOptions(digits=5)
        modified = dataclasses.replace(original, digits=2)
        assert original.digits == 5
        assert modified.digits == 2
        assert original is not modified

    def test_replace_revalidates(self) -> None:
        # ``dataclasses.replace`` re-runs ``__init__``, so the validation guard
        # also runs — invalid values via replace must raise the same error.
        opts = OptimizeOptions()
        with pytest.raises(InvalidOptionError):
            dataclasses.replace(opts, digits=0)


class TestOptparseBridge:
    """The internal ``_to_optparse_values`` shim must round-trip every field."""

    def test_every_field_preserved(self) -> None:
        opts = OptimizeOptions(
            digits=4,
            cdigits=2,
            shorten_ids=True,
            shorten_ids_prefix="x",
            indent_type="tab",
            allow_xml_entities=True,
            max_input_bytes=2048,
        )
        values = opts._to_optparse_values()
        assert values.digits == 4
        assert values.cdigits == 2
        assert values.shorten_ids is True
        assert values.shorten_ids_prefix == "x"
        assert values.indent_type == "tab"
        assert values.allow_xml_entities is True
        assert values.max_input_bytes == 2048

    def test_cli_only_fields_initialized(self) -> None:
        # The legacy pipeline may reach for ``options.infilename`` /
        # ``outfilename`` even when called programmatically; the bridge
        # populates them with None to avoid AttributeError.
        values = OptimizeOptions()._to_optparse_values()
        assert values.infilename is None
        assert values.outfilename is None

    def test_works_through_public_optimize(self) -> None:
        # Smoke test: routing OptimizeOptions through the legacy pipeline must
        # produce a valid SVG. (The public ``optimize`` already accepts
        # OptimizeOptions in v1.0; this verifies the bridge is wired.)
        from svg_polish import optimize

        opts = OptimizeOptions(digits=3, strip_xml_prolog=True)
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="1.234567" y="2.345678" width="3" height="4"/></svg>'
        result = optimize(svg, opts)
        assert "<svg" in result
        # strip_xml_prolog=True must have removed the prolog
        assert not result.startswith("<?xml")

    def test_sanitize_options_accepts_optimize_options(self) -> None:
        # ``sanitize_options`` is the internal entry point used inside the
        # pipeline and downstream tooling; it must accept an
        # OptimizeOptions directly (covers the isinstance fast-path).
        from svg_polish.optimizer import sanitize_options

        opts = OptimizeOptions(digits=2, shorten_ids=True)
        sanitized = sanitize_options(opts)
        assert sanitized.digits == 2
        assert sanitized.shorten_ids is True
