"""Thread-safety tests for the optimizer (Sprint 2, phase V1).

Validates that concurrent calls to :func:`scour_string` from many threads with
mixed precision settings produce byte-exact-correct results — i.e. no thread's
``ScouringPrecision`` state leaks into another's output.

Also exercises :func:`precision_scope` directly: nested scopes, exceptions
mid-scope, and isolation of ``ctx`` / ``ctx_c`` between threads.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from svg_polish.optimizer import generate_default_options, scour_string
from svg_polish.types import _precision, precision_scope

# A reasonably non-trivial SVG with float coordinates that are sensitive to
# precision settings — different ``digits`` values produce visibly different
# outputs, so we can detect cross-thread bleed.
SAMPLE_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M1.234567 9.876543 L2.345678 8.765432 Q3.456789 7.654321 4.567890 6.543210'/>"
    "<rect x='10.123456' y='20.234567' width='30.345678' height='40.456789'/>"
    "</svg>"
)


def _optimize_with_digits(digits: int) -> str:
    opts = generate_default_options()
    opts.digits = digits
    opts.cdigits = digits
    return scour_string(SAMPLE_SVG, opts)


class TestThreadIsolation:
    """Concurrent calls do not leak precision state across threads."""

    def test_concurrent_calls_match_sequential_baseline(self) -> None:
        """Each (digits) result under load matches the result run alone."""
        # Build a baseline: serial run for each digits value.
        baselines = {d: _optimize_with_digits(d) for d in (3, 5, 7)}

        # Run a mixed workload across 8 threads, 100 calls each.
        digits_pattern = [3, 5, 7] * 100  # 300 calls, 8 workers ⇒ heavy interleaving
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_optimize_with_digits, digits_pattern))

        for digits, observed in zip(digits_pattern, results, strict=True):
            assert observed == baselines[digits], (
                f"thread-local precision leaked: digits={digits} produced a non-baseline result"
            )

    def test_each_thread_sees_its_own_precision_setting(self) -> None:
        """A thread requesting digits=N sees ``_precision.ctx.prec == N`` even
        while another thread is concurrently inside its own ``precision_scope``.
        """
        # Use a barrier so all worker threads enter precision_scope simultaneously,
        # then read _precision.ctx.prec while every other thread is still inside
        # its own scope. If thread-local were broken, the readers would race and
        # observe each other's values.
        n_workers = 8
        barrier = threading.Barrier(n_workers)

        def worker(prec: int) -> int:
            with precision_scope(prec, prec):
                barrier.wait()  # all threads inside precision_scope concurrently
                return _precision.ctx.prec

        precs = [3, 4, 5, 6, 7, 8, 9, 10]
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            observed = list(pool.map(worker, precs))

        assert observed == precs, "thread-local precision was visible across threads"


class TestPrecisionScope:
    """``precision_scope`` correctness on the calling thread."""

    def test_restores_previous_contexts(self) -> None:
        original_ctx = _precision.ctx
        original_ctx_c = _precision.ctx_c
        with precision_scope(2, 3):
            assert _precision.ctx.prec == 2
            assert _precision.ctx_c.prec == 3
        assert _precision.ctx is original_ctx
        assert _precision.ctx_c is original_ctx_c

    def test_nested_scopes_unwind_in_lifo_order(self) -> None:
        with precision_scope(2, 2):
            outer_ctx = _precision.ctx
            with precision_scope(8, 8):
                assert _precision.ctx.prec == 8
            assert _precision.ctx is outer_ctx
            assert _precision.ctx.prec == 2

    def test_restores_on_exception(self) -> None:
        before = _precision.ctx
        with pytest.raises(RuntimeError), precision_scope(99, 99):
            raise RuntimeError("boom")
        assert _precision.ctx is before

    def test_does_not_touch_default_decimal_context(self) -> None:
        """Lowering the default Decimal context would break ``Decimal.quantize``."""
        import decimal

        before = decimal.getcontext().prec
        with precision_scope(2, 2):
            assert decimal.getcontext().prec == before
        assert decimal.getcontext().prec == before


class TestNestedScourString:
    """Nested ``scour_string`` calls do not corrupt each other's precision."""

    def test_nested_call_preserves_outer_precision(self) -> None:
        outer_opts = generate_default_options()
        outer_opts.digits = 7
        outer_opts.cdigits = 7

        inner_opts = generate_default_options()
        inner_opts.digits = 2
        inner_opts.cdigits = 2

        captured: dict[str, int] = {}

        def hook_after_inner_call() -> None:
            # Run inner scour_string from inside the outer's scope (simulated
            # by being called *between* the inner one and a subsequent assert).
            scour_string(SAMPLE_SVG, inner_opts)

        with precision_scope(outer_opts.digits, outer_opts.cdigits):
            captured["outer_before"] = _precision.ctx.prec
            hook_after_inner_call()
            captured["outer_after"] = _precision.ctx.prec

        assert captured["outer_before"] == captured["outer_after"] == 7
