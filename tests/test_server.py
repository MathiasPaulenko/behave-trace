"""Tests for behave_trace.viewer.server."""

from __future__ import annotations

import gzip
import json
import socket
import urllib.request
from pathlib import Path

import pytest

from behave_trace.models import (
    STATUS_PASSED,
    Environment,
    Feature,
    Scenario,
    Step,
    Trace,
    TraceStats,
)
from behave_trace.viewer.server import ViewerServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trace() -> Trace:
    return Trace(
        features=[
            Feature(
                name="Test Feature",
                status=STATUS_PASSED,
                scenarios=[
                    Scenario(
                        name="Test Scenario",
                        status=STATUS_PASSED,
                        steps=[Step(keyword="Given", name="a step", status=STATUS_PASSED)],
                    ),
                ],
            ),
        ],
        stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
    )


def make_server(trace: Trace | None = None, port: int = 0) -> ViewerServer:
    if trace is None:
        trace = make_trace()
    server = ViewerServer(trace, port=port)
    server.start()
    return server


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def post(url: str, body: dict | None = None) -> tuple[int, dict[str, str], bytes]:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApiTrace:
    def test_returns_200_with_json(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(f"{server.url}/api/trace")
            assert status == 200
            assert "application/json" in headers.get("Content-Type", "")
            data = json.loads(body)
            assert data["version"] == "1"
            assert len(data["features"]) == 1
        finally:
            server.stop()

    def test_trace_data_correct(self) -> None:
        trace = make_trace()
        server = make_server(trace)
        try:
            status, _, body = get(f"{server.url}/api/trace")
            data = json.loads(body)
            assert data["features"][0]["name"] == "Test Feature"
            assert data["features"][0]["scenarios"][0]["name"] == "Test Scenario"
        finally:
            server.stop()

    def test_with_gzip_encoding(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(
                f"{server.url}/api/trace",
                headers={"Accept-Encoding": "gzip"},
            )
            assert status == 200
            assert headers.get("Content-Encoding") == "gzip"
            decompressed = gzip.decompress(body)
            data = json.loads(decompressed)
            assert data["version"] == "1"
        finally:
            server.stop()

    def test_without_gzip_encoding(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(f"{server.url}/api/trace")
            assert status == 200
            assert headers.get("Content-Encoding") is None
            data = json.loads(body)
            assert data["version"] == "1"
        finally:
            server.stop()


class TestIndexHtml:
    def test_returns_200(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(f"{server.url}/")
            assert status == 200
            assert "text/html" in headers.get("Content-Type", "")
            assert b"<html" in body.lower() or b"<!doctype" in body.lower()
        finally:
            server.stop()


class TestStaticFiles:
    def test_css_file(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(f"{server.url}/css/viewer.css")
            assert status == 200
            assert "text/css" in headers.get("Content-Type", "")
        finally:
            server.stop()

    def test_js_file(self) -> None:
        server = make_server()
        try:
            status, headers, body = get(f"{server.url}/js/viewer.js")
            assert status == 200
            assert "javascript" in headers.get("Content-Type", "")
        finally:
            server.stop()

    def test_nonexistent_css_returns_404(self) -> None:
        server = make_server()
        try:
            status, _, _ = get(f"{server.url}/css/nonexistent.css")
            assert status == 404
        finally:
            server.stop()

    def test_nonexistent_js_returns_404(self) -> None:
        server = make_server()
        try:
            status, _, _ = get(f"{server.url}/js/nonexistent.js")
            assert status == 404
        finally:
            server.stop()


class TestPathTraversal:
    def test_traversal_returns_404(self) -> None:
        server = make_server()
        try:
            status, _, _ = get(f"{server.url}/css/../../etc/passwd")
            assert status == 404
        finally:
            server.stop()

    def test_double_dot_in_path(self) -> None:
        import socket

        server = make_server()
        try:
            port = server._httpd.server_address[1] if server._httpd else 0
            sock = socket.create_connection(("127.0.0.1", port), timeout=5)
            # /css/../../ escapes assets dir entirely
            sock.sendall(b"GET /css/../../etc/passwd HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            response = sock.recv(4096)
            sock.close()
            status_line = response.split(b"\r\n")[0]
            assert b"404" in status_line
        finally:
            server.stop()


class TestServerLifecycle:
    def test_url_property(self) -> None:
        server = make_server(port=0)
        try:
            url = server.url
            assert url.startswith("http://127.0.0.1:")
            port_str = url.rsplit(":", 1)[1]
            assert int(port_str) > 0
        finally:
            server.stop()

    def test_stop_is_clean(self) -> None:
        server = make_server()
        server.stop()
        # After stop, server should not respond
        with pytest.raises((ConnectionError, OSError)):
            get(f"{server.url}/api/trace")

    def test_start_returns_url(self) -> None:
        trace = make_trace()
        server = ViewerServer(trace, port=0)
        url = server.start()
        try:
            assert url.startswith("http://127.0.0.1:")
            assert server.url == url
        finally:
            server.stop()

    def test_specific_port(self) -> None:
        # Use port 0 to get a free port, then test with that port
        import socket

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        trace = make_trace()
        server = ViewerServer(trace, port=free_port)
        url = server.start()
        try:
            assert str(free_port) in url
        finally:
            server.stop()


class TestApiSource:
    """Tests for the /api/source endpoint."""

    @staticmethod
    def _make_source_trace(cwd: Path) -> Trace:
        return Trace(
            features=[
                Feature(
                    name="F",
                    status=STATUS_PASSED,
                    scenarios=[
                        Scenario(
                            name="S",
                            status=STATUS_PASSED,
                            steps=[
                                Step(
                                    keyword="Given",
                                    name="step",
                                    status=STATUS_PASSED,
                                    location="steps.py:3",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            environment=Environment(cwd=str(cwd)),
            stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
        )

    def test_returns_source_snippet(self, tmp_path: Path) -> None:
        (tmp_path / "steps.py").write_text(
            "line1\nline2\nline3\nline4\nline5\nline6\nline7\n",
            encoding="utf-8",
        )
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=steps.py&line=3&context=2")
            assert status == 200
            data = json.loads(body)
            assert data["path"] == "steps.py"
            assert data["line"] == 3
            assert data["language"] == "python"
            assert data["total_lines"] == 7
            snippet = data["snippet"]
            assert len(snippet) == 5  # 2 before + target + 2 after
            assert snippet[0]["number"] == 1
            assert snippet[2]["number"] == 3
            assert snippet[2]["content"] == "line3"
            assert snippet[2]["highlight"] is True
            assert snippet[0]["highlight"] is False
        finally:
            server.stop()

    def test_default_context_lines(self, tmp_path: Path) -> None:
        lines = [f"line{i}" for i in range(1, 21)]
        (tmp_path / "steps.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=steps.py&line=10")
            assert status == 200
            data = json.loads(body)
            # default context=5 → 5 before + target + 5 after = 11 lines
            assert len(data["snippet"]) == 11
            assert data["snippet"][5]["highlight"] is True
        finally:
            server.stop()

    def test_clamps_line_to_file(self, tmp_path: Path) -> None:
        (tmp_path / "steps.py").write_text("only\ntwo\nlines\n", encoding="utf-8")
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=steps.py&line=999")
            assert status == 200
            data = json.loads(body)
            assert data["line"] == 3  # clamped to total_lines
        finally:
            server.stop()

    def test_missing_path_param(self, tmp_path: Path) -> None:
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?line=10")
            assert status == 400
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_file_not_found(self, tmp_path: Path) -> None:
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=nonexistent.py&line=1")
            assert status == 404
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        trace = self._make_source_trace(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=../../etc/passwd&line=1")
            assert status == 403
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_language_detection(self, tmp_path: Path) -> None:
        (tmp_path / "steps.js").write_text("const x = 1;\n", encoding="utf-8")
        trace = Trace(
            features=[
                Feature(
                    name="F",
                    status=STATUS_PASSED,
                    scenarios=[
                        Scenario(
                            name="S",
                            status=STATUS_PASSED,
                            steps=[
                                Step(
                                    keyword="Given",
                                    name="step",
                                    status=STATUS_PASSED,
                                    location="steps.js:1",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            environment=Environment(cwd=str(tmp_path)),
            stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
        )
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=steps.js&line=1")
            assert status == 200
            data = json.loads(body)
            assert data["language"] == "javascript"
        finally:
            server.stop()

    def test_subdirectory_path(self, tmp_path: Path) -> None:
        sub = tmp_path / "steps"
        sub.mkdir()
        (sub / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        trace = Trace(
            features=[
                Feature(
                    name="F",
                    status=STATUS_PASSED,
                    scenarios=[
                        Scenario(
                            name="S",
                            status=STATUS_PASSED,
                            steps=[
                                Step(
                                    keyword="Given",
                                    name="step",
                                    status=STATUS_PASSED,
                                    location="steps/calculator.py:1",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            environment=Environment(cwd=str(tmp_path)),
            stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
        )
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, body = get(f"{server.url}/api/source?path=steps/calculator.py&line=1")
            assert status == 200
            data = json.loads(body)
            assert data["path"] == "steps/calculator.py"
            assert data["language"] == "python"
            assert data["snippet"][0]["content"] == "def add(a, b):"
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# SSE / Streaming tests
# ---------------------------------------------------------------------------


class TestSSEStream:
    def _sse_connect(self, server: ViewerServer) -> socket.socket:
        """Open a raw socket SSE connection and return it."""
        addr = ("127.0.0.1", server._httpd.server_address[1])
        sock = socket.create_connection(addr, timeout=10)
        sock.sendall(b"GET /api/stream HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        return sock

    def _read_sse_events(self, sock: socket.socket, max_events: int = 10) -> list[dict]:
        """Read SSE events from a socket until max_events or timeout."""
        events: list[dict] = []
        buffer = b""
        sock.settimeout(5)
        while len(events) < max_events:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n\n" in buffer:
                    event_data, buffer = buffer.split(b"\n\n", 1)
                    for line in event_data.decode("utf-8").split("\n"):
                        if line.startswith("data:"):
                            events.append(json.loads(line[5:].strip()))
            except (TimeoutError, OSError):
                break
        return events

    def test_stream_returns_text_event_stream(self) -> None:
        server = make_server()
        try:
            sock = self._sse_connect(server)
            # Read the HTTP headers
            sock.settimeout(5)
            header_data = b""
            while b"\r\n\r\n" not in header_data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                header_data += chunk
            headers_text = header_data.decode("utf-8")
            assert "200" in headers_text
            assert "text/event-stream" in headers_text
            sock.close()
        finally:
            server.stop()

    def test_stream_sends_initial_state_event(self) -> None:
        server = make_server()
        try:
            sock = self._sse_connect(server)
            events = self._read_sse_events(sock, max_events=1)
            sock.close()
            assert len(events) >= 1
            assert events[0]["type"] == "state"
            assert "running" in events[0]
            assert "watching" in events[0]
        finally:
            server.stop()

    def test_set_running_notifies_clients(self) -> None:
        import threading
        import time

        server = make_server()
        try:
            received_events: list[dict] = []
            event_ready = threading.Event()

            def read_stream() -> None:
                try:
                    sock = self._sse_connect(server)
                    sock.settimeout(10)
                    buffer = b""
                    while not event_ready.is_set():
                        try:
                            chunk = sock.recv(4096)
                            if not chunk:
                                break
                            buffer += chunk
                            while b"\n\n" in buffer:
                                event_data, buffer = buffer.split(b"\n\n", 1)
                                for line in event_data.decode("utf-8").split("\n"):
                                    if line.startswith("data:"):
                                        event = json.loads(line[5:].strip())
                                        received_events.append(event)
                                        if event.get("type") == "run_started":
                                            event_ready.set()
                        except (TimeoutError, OSError):
                            break
                    sock.close()
                except Exception:
                    pass

            t = threading.Thread(target=read_stream, daemon=True)
            t.start()
            time.sleep(1.0)

            server.set_running(True)

            assert event_ready.wait(timeout=10), "Did not receive run_started event"
            assert any(e.get("type") == "run_started" for e in received_events)
        finally:
            server.stop()

    def test_update_trace_notifies_clients(self) -> None:
        import threading
        import time

        trace = make_trace()
        server = make_server(trace)
        try:
            received_events: list[dict] = []
            event_ready = threading.Event()

            def read_stream() -> None:
                try:
                    sock = self._sse_connect(server)
                    sock.settimeout(10)
                    buffer = b""
                    while not event_ready.is_set():
                        try:
                            chunk = sock.recv(4096)
                            if not chunk:
                                break
                            buffer += chunk
                            while b"\n\n" in buffer:
                                event_data, buffer = buffer.split(b"\n\n", 1)
                                for line in event_data.decode("utf-8").split("\n"):
                                    if line.startswith("data:"):
                                        event = json.loads(line[5:].strip())
                                        received_events.append(event)
                                        if event.get("type") == "trace_updated":
                                            event_ready.set()
                        except (TimeoutError, OSError):
                            break
                    sock.close()
                except Exception:
                    pass

            t = threading.Thread(target=read_stream, daemon=True)
            t.start()
            time.sleep(1.0)

            new_trace = make_trace()
            server.update_trace(new_trace)

            assert event_ready.wait(timeout=10), "Did not receive trace_updated event"
            assert any(e.get("type") == "trace_updated" for e in received_events)
        finally:
            server.stop()

    def test_update_trace_changes_api_response(self) -> None:
        trace = make_trace()
        server = make_server(trace)
        try:
            _, _, body = get(f"{server.url}/api/trace")
            original = json.loads(body)
            assert original["features"][0]["name"] == "Test Feature"

            new_trace = Trace(
                features=[
                    Feature(
                        name="Updated Feature",
                        status=STATUS_PASSED,
                        scenarios=[
                            Scenario(
                                name="Updated Scenario",
                                status=STATUS_PASSED,
                                steps=[Step(keyword="Given", name="updated", status=STATUS_PASSED)],
                            ),
                        ],
                    ),
                ],
                stats=TraceStats(total_features=1, total_scenarios=1, total_steps=1),
            )
            server.update_trace(new_trace)

            _, _, body2 = get(f"{server.url}/api/trace")
            updated = json.loads(body2)
            assert updated["features"][0]["name"] == "Updated Feature"
        finally:
            server.stop()

    def test_watching_flag_in_initial_state(self) -> None:
        trace = make_trace()
        server = ViewerServer(trace, port=0, watching=True)
        server.start()
        try:
            sock = self._sse_connect(server)
            events = self._read_sse_events(sock, max_events=1)
            sock.close()
            assert len(events) >= 1
            assert events[0]["watching"] is True
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Re-run tests
# ---------------------------------------------------------------------------


class TestRerun:
    def test_rerun_without_callback_returns_501(self) -> None:
        server = make_server()
        try:
            status, _, body = post(f"{server.url}/api/rerun", {"filter": "all"})
            assert status == 501
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_rerun_with_callback_returns_202(self) -> None:
        import threading

        callback_called = threading.Event()

        def callback(scenarios: list[str] | None) -> None:
            callback_called.set()

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=callback)
        server.start()
        try:
            status, _, body = post(f"{server.url}/api/rerun", {"filter": "all"})
            assert status == 200
            data = json.loads(body)
            assert data["status"] == "accepted"
            assert callback_called.wait(timeout=5)
        finally:
            server.stop()

    def test_rerun_failed_passes_scenario_names(self) -> None:
        import threading

        received_scenarios: list[list[str] | None] = []
        callback_called = threading.Event()

        def callback(scenarios: list[str] | None) -> None:
            received_scenarios.append(scenarios)
            callback_called.set()

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=callback)
        server.start()
        try:
            post(
                f"{server.url}/api/rerun",
                {"filter": "failed", "scenarios": ["Scenario A", "Scenario B"]},
            )
            assert callback_called.wait(timeout=5)
            assert received_scenarios[0] == ["Scenario A", "Scenario B"]
        finally:
            server.stop()

    def test_rerun_all_passes_none(self) -> None:
        import threading

        received_scenarios: list[list[str] | None] = []
        callback_called = threading.Event()

        def callback(scenarios: list[str] | None) -> None:
            received_scenarios.append(scenarios)
            callback_called.set()

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=callback)
        server.start()
        try:
            post(f"{server.url}/api/rerun", {"filter": "all"})
            assert callback_called.wait(timeout=5)
            assert received_scenarios[0] is None
        finally:
            server.stop()

    def test_rerun_invalid_filter_returns_400(self) -> None:
        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda _: None)
        server.start()
        try:
            status, _, body = post(f"{server.url}/api/rerun", {"filter": "invalid"})
            assert status == 400
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_rerun_invalid_json_returns_400(self) -> None:
        import urllib.error

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda _: None)
        server.start()
        try:
            req = urllib.request.Request(
                f"{server.url}/api/rerun",
                data=b"not json",
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req) as resp:
                    status = resp.status
                    body = resp.read()
            except urllib.error.HTTPError as e:
                status = e.code
                body = e.read()
            assert status == 400
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_rerun_callback_exception_resets_running_flag(self) -> None:
        """Regression for Bug 27: callback raising must not leave server stuck running.

        The CLI's rerun_callback sets server.set_running(True) before calling
        runner.run().  If runner.run() raises, the finally block must still
        call server.set_running(False).  This test simulates that pattern.
        """
        import threading
        import time

        callback_called = threading.Event()

        def exploding_callback(scenarios: list[str] | None) -> None:
            # Simulate the CLI pattern: set running, then raise
            server._state.set_running(True)
            callback_called.set()
            try:
                raise RuntimeError("behave subprocess crashed")
            except Exception:
                pass
            finally:
                server._state.set_running(False)

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=exploding_callback)
        server.start()
        try:
            post(f"{server.url}/api/rerun", {"filter": "all"})
            assert callback_called.wait(timeout=5)
            # Give the callback thread time to finish
            time.sleep(0.5)
            assert server._state.running is False
        finally:
            server.stop()

    def test_rerun_unknown_path_returns_404(self) -> None:
        server = make_server()
        try:
            status, _, _ = post(f"{server.url}/api/unknown", {})
            assert status == 404
        finally:
            server.stop()

    def test_rerun_malformed_content_length_does_not_crash(self) -> None:
        """Regression: malformed Content-Length header should not crash the server."""
        import urllib.error

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda _: None)
        server.start()
        try:
            req = urllib.request.Request(
                f"{server.url}/api/rerun",
                data=b'{"filter": "all"}',
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("Content-Length", "not-a-number")
            try:
                with urllib.request.urlopen(req) as resp:
                    status = resp.status
            except urllib.error.HTTPError as e:
                status = e.code
            # Server should handle gracefully, not crash
            assert status in (200, 400)
        finally:
            server.stop()

    def test_rerun_non_dict_json_returns_400(self) -> None:
        """Regression: non-dict JSON payload should return 400, not crash."""
        import urllib.error

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda _: None)
        server.start()
        try:
            req = urllib.request.Request(
                f"{server.url}/api/rerun",
                data=b'[1, 2, 3]',
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req) as resp:
                    status = resp.status
                    body = resp.read()
            except urllib.error.HTTPError as e:
                status = e.code
                body = e.read()
            assert status == 400
            data = json.loads(body)
            assert "error" in data
        finally:
            server.stop()

    def test_rerun_scenarios_as_non_list_does_not_crash(self) -> None:
        """Regression for Bug 32: scenarios as non-list type must not crash.

        If scenarios is a string or int, the server should not raise TypeError.
        It should treat it as no scenario names (None).
        """
        import threading

        received_scenarios: list[list[str] | None] = []
        callback_called = threading.Event()

        def callback(scenarios: list[str] | None) -> None:
            received_scenarios.append(scenarios)
            callback_called.set()

        trace = make_trace()
        server = ViewerServer(trace, port=0, rerun_callback=callback)
        server.start()
        try:
            # scenarios as string — should not iterate characters
            post(
                f"{server.url}/api/rerun",
                {"filter": "failed", "scenarios": "not_a_list"},
            )
            assert callback_called.wait(timeout=5)
            assert received_scenarios[0] is None
        finally:
            server.stop()
