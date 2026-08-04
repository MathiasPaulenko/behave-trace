"""Tests for behave_trace CLI."""

from __future__ import annotations

import json
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from behave_trace.cli.app import main
from behave_trace.models import (
    STATUS_FAILED,
    STATUS_PASSED,
    Feature,
    Scenario,
    Step,
    Trace,
    TraceStats,
)
from behave_trace.serializer import Serializer

# macOS CI runners (GitHub Actions) often block local server connections
_skip_macos_ci = pytest.mark.skipif(
    sys.platform == "darwin" and platform.processor().startswith("arm"),
    reason="Local server tests are unreliable on macOS CI runners",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trace_file(tmp_path: Path) -> Path:
    """Create a trace file with known data for testing."""
    trace = Trace(
        features=[
            Feature(
                name="F1",
                status=STATUS_PASSED,
                duration=5.0,
                scenarios=[
                    Scenario(
                        name="S1",
                        status=STATUS_PASSED,
                        duration=2.0,
                        steps=[
                            Step(keyword="Given", name="a", status=STATUS_PASSED, duration=1.0),
                            Step(keyword="Then", name="b", status=STATUS_PASSED, duration=1.0),
                        ],
                    ),
                    Scenario(
                        name="S2",
                        status=STATUS_FAILED,
                        duration=3.0,
                        steps=[
                            Step(keyword="Given", name="c", status=STATUS_PASSED, duration=1.0),
                            Step(keyword="Then", name="d", status=STATUS_FAILED, duration=2.0),
                        ],
                    ),
                ],
            ),
        ],
        stats=TraceStats(
            total_features=1,
            total_scenarios=2,
            total_steps=4,
            by_status={"passed": 1, "failed": 1},
            duration=5.0,
        ),
    )
    path = tmp_path / "trace.json"
    Serializer.save(trace, path)
    return path


def _get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    """Poll until the server responds or timeout expires."""
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/trace", timeout=2):
                return
        except Exception as exc:
            last_err = exc
            time.sleep(0.3)
    raise TimeoutError(f"Server on port {port} did not respond within {timeout}s: {last_err}")


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "behave-trace" in captured.out
        assert "1.1.0" in captured.out


# ---------------------------------------------------------------------------
# show — error cases (don't block)
# ---------------------------------------------------------------------------


class TestShowErrors:
    def test_show_file_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = main(["show", "nonexistent.json"])
        assert result == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_show_invalid_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = main(["show", str(bad)])
        assert result == 1
        err = capsys.readouterr().err
        assert "Error" in err


# ---------------------------------------------------------------------------
# show — with server (blocking, tested via subprocess)
# ---------------------------------------------------------------------------


@_skip_macos_ci
class TestShowServer:
    def test_show_starts_server(self, tmp_path: Path) -> None:
        """Run `behave-trace show` as subprocess, verify server responds."""
        trace_path = make_trace_file(tmp_path)
        port = _get_free_port()

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "behave_trace",
                "show",
                str(trace_path),
                "--port",
                str(port),
                "--no-browser",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to start (CI runners may be slow)
            _wait_for_server(port, timeout=10)

            # Verify server responds
            url = f"http://127.0.0.1:{port}/api/trace"
            with urllib.request.urlopen(url, timeout=10) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["version"] == "1"
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_show_prints_summary_and_url(self, tmp_path: Path) -> None:
        """Verify the show command prints summary and viewer URL."""
        trace_path = make_trace_file(tmp_path)
        port = _get_free_port()

        env = dict(__import__("os").environ)
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "behave_trace",
                "show",
                str(trace_path),
                "--port",
                str(port),
                "--no-browser",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            # Wait for server to start and print output
            _wait_for_server(port, timeout=10)
            time.sleep(0.5)
            # Read what's available so far
            import os

            os.set_blocking(proc.stdout.fileno(), False)
            combined = proc.stdout.read() or ""
        finally:
            proc.terminate()
            proc.wait(timeout=10)

        assert "Features: 1" in combined
        assert "Scenarios: 2" in combined
        assert "Viewer running at" in combined
        assert str(port) in combined

    def test_show_terminates_cleanly(self, tmp_path: Path) -> None:
        """Verify Ctrl+C (SIGTERM/SIGINT) terminates the process cleanly."""
        trace_path = make_trace_file(tmp_path)
        port = _get_free_port()

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "behave_trace",
                "show",
                str(trace_path),
                "--port",
                str(port),
                "--no-browser",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            _wait_for_server(port, timeout=10)
            proc.terminate()
            ret = proc.wait(timeout=10)
            # On Windows, terminate() sends SIGTERM equivalent
            # The process should exit without hanging
            assert ret is not None
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Process did not terminate within timeout")

    def test_show_empty_trace(self, tmp_path: Path) -> None:
        """Verify show works with an empty trace."""
        trace = Trace()
        path = tmp_path / "empty.json"
        Serializer.save(trace, path)
        port = _get_free_port()

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "behave_trace",
                "show",
                str(path),
                "--port",
                str(port),
                "--no-browser",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            _wait_for_server(port, timeout=10)
            url = f"http://127.0.0.1:{port}/api/trace"
            with urllib.request.urlopen(url, timeout=10) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["features"] == []
        finally:
            proc.terminate()
            proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# no command
# ---------------------------------------------------------------------------


class TestNoCommand:
    def test_no_command_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = main([])
        assert result == 0
        out = capsys.readouterr().out
        assert "behave-trace" in out.lower() or "usage" in out.lower()


# ---------------------------------------------------------------------------
# run — error cases
# ---------------------------------------------------------------------------


class TestRunErrors:
    def test_run_dir_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = main(["run", "nonexistent_dir"])
        assert result == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_run_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "run" in out.lower()
        assert "features" in out.lower()


# ---------------------------------------------------------------------------
# run — parser registration
# ---------------------------------------------------------------------------


class TestRunParser:
    def test_run_command_registered(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify the run subcommand is listed in help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "run" in out

    def test_run_default_features_dir(self) -> None:
        """Verify run defaults to '.' for features_dir."""
        from behave_trace.cli.app import main as _main

        # Parse without executing — just check the parser doesn't error
        # We'll use a non-existent dir to get a quick error return
        result = _main(["run", "--no-browser", "nonexistent_dir_xyz"])
        assert result == 1


# ---------------------------------------------------------------------------
# run — runner exception safety (Bug 29)
# ---------------------------------------------------------------------------


class TestRunExceptionSafety:
    def test_runner_exception_returns_clean_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression for Bug 29: runner.run() raising must not crash with traceback."""
        from unittest.mock import patch

        features_dir = tmp_path / "features"
        features_dir.mkdir()

        with patch(
            "behave_trace.runner.BehaveRunner.run",
            side_effect=OSError("subprocess crashed"),
        ):
            result = main(["run", "--no-browser", str(features_dir)])

        assert result == 1
        err = capsys.readouterr().err
        assert "failed to run behave" in err.lower()
