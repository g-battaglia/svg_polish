"""Tests for :mod:`svg_polish.cli` (Sprint 3, M2).

Covers argument parsing, validation errors, file I/O helpers
(:func:`maybe_gziped_file`, :func:`get_in_out`), the report formatter
:func:`generate_report`, and the end-to-end :func:`run` entry point.
"""

from __future__ import annotations

import gzip
import io
import pathlib
import sys
from unittest import mock

import pytest

from svg_polish.cli import (
    HeaderedFormatter,
    generate_report,
    get_in_out,
    maybe_gziped_file,
    parse_args,
    run,
    start,
)
from svg_polish.stats import ScourStats

SAMPLE_SVG = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<rect x="0" y="0" width="10" height="10" fill="#ff0000"/>'
    "</svg>"
)


class TestHeaderedFormatter:
    """The custom optparse formatter must prepend app/version/copyright."""

    def test_format_usage_prepends_header(self) -> None:
        formatter = HeaderedFormatter(max_help_position=33)
        result = formatter.format_usage("Usage: foo")
        # Header lines (APP, VER, COPYRIGHT) all appear before "Usage: foo"
        assert "Usage: foo" in result
        # Three newlines: APP+VER, COPYRIGHT, then the usage body — so the
        # rendered string contains at least three line breaks.
        assert result.count("\n") >= 3


class TestParseArgs:
    """Argument parsing covers happy path and validation guards."""

    def test_defaults(self) -> None:
        opts = parse_args([])
        assert opts.digits == 5
        assert opts.cdigits == -1
        assert opts.quiet is False
        assert opts.verbose is False

    def test_positional_input_filename(self) -> None:
        opts = parse_args(["in.svg"])
        assert opts.infilename == "in.svg"

    def test_positional_input_and_output(self) -> None:
        opts = parse_args(["in.svg", "out.svg"])
        assert opts.infilename == "in.svg"
        assert opts.outfilename == "out.svg"

    def test_extra_positional_errors_out(self) -> None:
        # optparse calls sys.exit(2) on parser error — caught as SystemExit.
        with pytest.raises(SystemExit):
            parse_args(["a.svg", "b.svg", "c.svg"])

    def test_ignore_additional_args_skips_extra(self) -> None:
        # Drone mode for downstream tooling: extra positional args silently
        # discarded instead of triggering parser.error.
        opts = parse_args(["a.svg", "b.svg", "c.svg"], ignore_additional_args=True)
        assert opts.infilename == "a.svg"
        assert opts.outfilename == "b.svg"

    def test_negative_digits_rejected(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--set-precision=0"])

    def test_cdigits_clamped_when_higher_than_digits(self, capsys: pytest.CaptureFixture[str]) -> None:
        # When cdigits > digits, the parser warns on stderr and resets to -1
        # (sentinel meaning "use digits").
        opts = parse_args(["--set-precision=3", "--set-c-precision=9"])
        assert opts.cdigits == -1
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_invalid_indent_type_rejected(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--indent=zigzag"])

    def test_negative_nindent_rejected(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--nindent=-1"])

    def test_same_in_out_filename_rejected(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["-i", "x.svg", "-o", "x.svg"])

    def test_explicit_flags_propagate(self) -> None:
        opts = parse_args(
            [
                "--shorten-ids",
                "--strip-xml-prolog",
                "--allow-xml-entities",
                "--max-input-bytes=2048",
            ]
        )
        assert opts.shorten_ids is True
        assert opts.strip_xml_prolog is True
        assert opts.allow_xml_entities is True
        assert opts.max_input_bytes == 2048


class TestMaybeGzipedFile:
    """``maybe_gziped_file`` selects gzip backend by extension."""

    def test_plain_svg_uses_open(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "in.svg"
        f.write_text(SAMPLE_SVG)
        with maybe_gziped_file(str(f), "r") as handle:
            assert SAMPLE_SVG in handle.read()

    def test_svgz_extension_uses_gzip(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "in.svgz"
        with gzip.open(f, "wb") as gz:
            gz.write(SAMPLE_SVG.encode("utf-8"))
        with maybe_gziped_file(str(f), "rb") as handle:
            assert SAMPLE_SVG.encode("utf-8") in handle.read()

    def test_uppercase_svgz_also_recognised(self, tmp_path: pathlib.Path) -> None:
        # ``os.path.splitext`` is case-sensitive but the helper lowercases
        # before comparison; verify ".SVGZ" still triggers gzip.
        f = tmp_path / "in.SVGZ"
        with gzip.open(f, "wb") as gz:
            gz.write(SAMPLE_SVG.encode("utf-8"))
        with maybe_gziped_file(str(f), "rb") as handle:
            assert SAMPLE_SVG.encode("utf-8") in handle.read()


class TestGetInOut:
    """``get_in_out`` resolves file handles or falls back to stdin/stdout."""

    def test_file_paths_open_handles(self, tmp_path: pathlib.Path) -> None:
        infile = tmp_path / "in.svg"
        outfile = tmp_path / "out.svg"
        infile.write_text(SAMPLE_SVG)
        opts = parse_args([str(infile), str(outfile)])
        in_h, out_h = get_in_out(opts)
        try:
            assert in_h.read() == SAMPLE_SVG.encode("utf-8")
        finally:
            in_h.close()
            out_h.close()

    def test_no_input_falls_back_to_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pretend stdin is piped (not a TTY) so the helper proceeds to use
        # ``sys.stdin`` as the input source.
        fake_stdin = mock.MagicMock()
        fake_stdin.isatty.return_value = False
        fake_stdin.buffer = io.BytesIO(SAMPLE_SVG.encode("utf-8"))
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        opts = parse_args([])
        in_h, out_h = get_in_out(opts)
        # Output also defaulted to stdout (or its buffer).
        assert in_h is not None
        assert out_h is not None

    def test_tty_stdin_without_input_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # When stdin is a TTY and no file specified, the helper must abort
        # via parser.error → SystemExit.
        fake_stdin = mock.MagicMock()
        fake_stdin.isatty.return_value = True
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        opts = parse_args([])
        with pytest.raises(SystemExit):
            get_in_out(opts)


class TestGenerateReport:
    """``generate_report`` formats every counter on its own line."""

    def test_includes_every_counter(self) -> None:
        stats = ScourStats(num_elements_removed=42, num_bytes_saved_in_colors=7)
        report = generate_report(stats)
        # All key labels appear in the report.
        assert "Number of elements removed: 42" in report
        assert "Number of bytes saved in colors: 7" in report
        assert "Number of attributes removed: 0" in report

    def test_uses_os_linesep(self) -> None:
        import os as _os

        stats = ScourStats()
        report = generate_report(stats)
        assert _os.linesep in report


class TestStartAndRun:
    """End-to-end pipeline through ``start`` and the ``run`` entry point."""

    def test_start_writes_optimized_output(self, tmp_path: pathlib.Path) -> None:
        infile = tmp_path / "in.svg"
        outfile = tmp_path / "out.svg"
        infile.write_text(SAMPLE_SVG)
        opts = parse_args([str(infile), str(outfile)])
        in_h, out_h = get_in_out(opts)
        start(opts, in_h, out_h)
        assert b"<svg" in outfile.read_bytes()

    def test_start_quiet_suppresses_message(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        infile = tmp_path / "in.svg"
        outfile = tmp_path / "out.svg"
        infile.write_text(SAMPLE_SVG)
        opts = parse_args(["--quiet", str(infile), str(outfile)])
        in_h, out_h = get_in_out(opts)
        start(opts, in_h, out_h)
        captured = capsys.readouterr()
        # No "processed file" message when --quiet.
        assert "processed file" not in captured.out

    def test_start_verbose_emits_report(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        infile = tmp_path / "in.svg"
        outfile = tmp_path / "out.svg"
        infile.write_text(SAMPLE_SVG)
        opts = parse_args(["--verbose", str(infile), str(outfile)])
        in_h, out_h = get_in_out(opts)
        start(opts, in_h, out_h)
        captured = capsys.readouterr()
        assert "Number of elements removed" in captured.out

    def test_run_entry_point(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        infile = tmp_path / "in.svg"
        outfile = tmp_path / "out.svg"
        infile.write_text(SAMPLE_SVG)
        # Simulate ``svg-polish in.svg out.svg`` from the shell.
        monkeypatch.setattr(sys, "argv", ["svg-polish", str(infile), str(outfile)])
        run()
        assert b"<svg" in outfile.read_bytes()


class TestInstalledEntryPoint:
    """Regression guard against ``pyproject.toml:[project.scripts]`` drift.

    The in-process tests above import ``run`` directly, so they pass even
    when the project.scripts entry point points at a non-existent or
    renamed symbol. Those two paths ran out of sync once already
    (``svg_polish.optimizer:run`` → ``svg_polish.cli:run``); the checks in
    this class close that gap by exercising the wrapper script the way
    the shell does after ``pip install``.
    """

    def test_console_script_entry_point_resolves(self) -> None:
        """The entry-point string must load a callable.

        ``ep.load()`` performs the same ``import + getattr`` that the
        generated wrapper script runs at startup — if
        ``svg_polish.cli:run`` ever moves again, this test fails with the
        same ``ImportError`` the user would see on ``svg-polish --help``.
        """
        import importlib.metadata

        eps = importlib.metadata.entry_points(group="console_scripts")
        polish = [ep for ep in eps if ep.name == "svg-polish"]
        assert polish, "'svg-polish' console script not registered"
        assert len(polish) == 1
        (ep,) = polish
        assert ep.value == "svg_polish.cli:run", f"unexpected entry point: {ep.value}"
        loaded = ep.load()
        assert callable(loaded)

    def test_installed_binary_help_succeeds(self) -> None:
        """Invoking the wrapper binary on ``--help`` must exit 0.

        Belt-and-braces test: even if ``entry_points()`` above resolves,
        the wrapper shebang / Python-launcher contract on some platforms
        can still fail. This spawns a real process.
        """
        import shutil
        import subprocess

        binary = shutil.which("svg-polish")
        if binary is None:
            binary_path = pathlib.Path(sys.executable).parent / "svg-polish"
            if not binary_path.exists():
                pytest.skip("svg-polish not installed in this interpreter's bin dir")
            binary = str(binary_path)

        result = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"--help exited {result.returncode}\nstderr:\n{result.stderr}"
        assert "svg-polish" in result.stdout.lower()
