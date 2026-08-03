"""Tests for CLI `show` command with server integration."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from behave_trace.models import STATUS_PASSED, Feature, Scenario, Step, Trace, TraceStats
from behave_trace.serializer import Serializer


def _get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_trace_file(tmp_path: Path) -> Path:
    trace = Trace(
        features=[
            Feature(
                name="Show Test",
                status=STATUS_PASSED,
                scenarios=[
                    Scenario(
                        name="S1",
                        status=STATUS_PASSED,
                        steps=[Step(keyword="Given", name="step", status=STATUS_PASSED)],
                    ),
                ],
            ),
        ],
        stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
    )
    path = tmp_path / "trace.json"
    Serializer.save(trace, path)
    return path


class TestCliShowServer:
    def test_server_responds_200(self, tmp_path: Path) -> None:
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
            url = f"http://127.0.0.1:{port}/api/trace"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["version"] == "1"
                assert len(data["features"]) == 1
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_keyboard_interrupt_stops_cleanly(self, tmp_path: Path) -> None:
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
            assert ret is not None
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Process did not stop after terminate")

    def test_index_html_served(self, tmp_path: Path) -> None:
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
            url = f"http://127.0.0.1:{port}/"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                assert "text/html" in resp.headers.get("Content-Type", "")
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_port_in_use_error(self, tmp_path: Path) -> None:
        trace_path = make_trace_file(tmp_path)
        port = _get_free_port()

        # Occupy the port first
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        blocker.bind(("127.0.0.1", port))
        blocker.listen(1)

        try:
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
            ret = proc.wait(timeout=5)
            assert ret == 1
            stderr = proc.stderr.read()
            assert "cannot start server" in stderr.lower() or "error" in stderr.lower()
        finally:
            blocker.close()
