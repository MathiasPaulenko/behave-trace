"""Tests for behave_trace CLI."""

from __future__ import annotations

import json
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
        assert "0.1.0" in captured.out


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
            # Wait for server to start
            time.sleep(1.0)

            # Verify server responds
            url = f"http://127.0.0.1:{port}/api/trace"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["version"] == "1"
        finally:
            proc.terminate()
            proc.wait(timeout=5)

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
            time.sleep(1.5)
            # Read what's available so far
            import os

            os.set_blocking(proc.stdout.fileno(), False)
            combined = proc.stdout.read() or ""
        finally:
            proc.terminate()
            proc.wait(timeout=5)

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
            time.sleep(1.0)
            proc.terminate()
            ret = proc.wait(timeout=5)
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
            time.sleep(1.0)
            url = f"http://127.0.0.1:{port}/api/trace"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["features"] == []
        finally:
            proc.terminate()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# no command
# ---------------------------------------------------------------------------


class TestNoCommand:
    def test_no_command_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = main([])
        assert result == 0
        out = capsys.readouterr().out
        assert "behave-trace" in out.lower() or "usage" in out.lower()
