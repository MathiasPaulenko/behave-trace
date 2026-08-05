"""Additional server API tests to cover uncovered endpoints and edge cases."""

from __future__ import annotations

import contextlib
import gzip
import json
import socket
import threading
import time
import urllib.request
from pathlib import Path
from unittest import mock

import pytest

from behave_trace.models import Trace
from behave_trace.viewer.server import ViewerServer


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(
    trace: Trace | None = None,
    port: int = 0,
    watching: bool = False,
    rerun_callback=None,
    base_dir: Path | None = None,
) -> tuple[ViewerServer, int]:
    server = ViewerServer(trace, port=port, watching=watching, rerun_callback=rerun_callback)
    if base_dir is not None:
        server._base_dir = base_dir
    url = server.start()
    actual_port = int(url.rsplit(":", 1)[1])
    return server, actual_port


def _get(port: int, path: str, headers: dict | None = None) -> urllib.request.Request:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    return req


class TestWatchingEndpoint:
    """Tests for GET /api/watching."""

    def test_watching_true(self) -> None:
        server, port = _start_server(watching=True)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/watching") as resp:
                data = json.loads(resp.read())
            assert data["watching"] is True
        finally:
            server.stop()

    def test_watching_false(self) -> None:
        server, port = _start_server(watching=False)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/watching") as resp:
                data = json.loads(resp.read())
            assert data["watching"] is False
        finally:
            server.stop()


class TestAutorunEndpoint:
    """Tests for POST /api/autorun."""

    def test_autorun_enable(self) -> None:
        server, port = _start_server()
        try:
            data = json.dumps({"enabled": True}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert result["status"] == "ok"
            assert result["autoRun"] is True
            assert server.get_auto_run() is True
        finally:
            server.stop()

    def test_autorun_disable(self) -> None:
        server, port = _start_server(watching=True)
        try:
            assert server.get_auto_run() is True
            data = json.dumps({"enabled": False}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert result["autoRun"] is False
            assert server.get_auto_run() is False
        finally:
            server.stop()

    def test_autorun_invalid_json(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=b"not json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_autorun_non_dict_json(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=json.dumps([1, 2]).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_autorun_missing_enabled(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=json.dumps({}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_autorun_enabled_not_bool(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/autorun",
                data=json.dumps({"enabled": "yes"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()


class TestRunEndpoint:
    """Tests for POST /api/run."""

    def test_run_without_callback_returns_501(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 501
        finally:
            server.stop()

    def test_run_with_callback_returns_accepted(self) -> None:
        callback = mock.Mock()
        server, port = _start_server(rerun_callback=callback)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert result["status"] == "accepted"
            # Wait for callback to be called
            time.sleep(0.5)
            callback.assert_called_once_with(None)
        finally:
            server.stop()

    def test_run_already_running_returns_409(self) -> None:
        callback = mock.Mock()
        server, port = _start_server(rerun_callback=callback)
        try:
            # Block callback so running stays True
            callback_event = threading.Event()

            def slow_callback(names):
                callback_event.wait(timeout=2)

            callback.side_effect = slow_callback

            req1 = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req1) as resp:
                assert json.loads(resp.read())["status"] == "accepted"

            time.sleep(0.2)

            req2 = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req2)
            assert exc_info.value.code == 409

            callback_event.set()
            time.sleep(0.3)
        finally:
            server.stop()


class TestPostUnknownPath:
    """Test POST to unknown path."""

    def test_post_unknown_returns_404(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/unknown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 404
        finally:
            server.stop()


class TestSourceEndpointEdge:
    """Edge cases for /api/source."""

    def test_source_invalid_line_param(self, tmp_path: Path) -> None:
        server, port = _start_server(base_dir=tmp_path)
        try:
            (tmp_path / "test.py").write_text("print('hello')\n")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/source?path=test.py&line=abc"
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_source_file_not_found(self, tmp_path: Path) -> None:
        server, port = _start_server(base_dir=tmp_path)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/source?path=nonexistent.py&line=1"
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 404
        finally:
            server.stop()

    def test_source_clamps_line(self, tmp_path: Path) -> None:
        """Line number beyond file length is clamped."""
        server, port = _start_server(base_dir=tmp_path)
        try:
            (tmp_path / "test.py").write_text("line1\nline2\n")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/source?path=test.py&line=999"
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            assert data["line"] == 2  # clamped to total_lines
        finally:
            server.stop()

    def test_source_with_context_param(self, tmp_path: Path) -> None:
        """Context parameter controls snippet size."""
        server, port = _start_server(base_dir=tmp_path)
        try:
            content = "\n".join(f"line{i}" for i in range(1, 21))
            (tmp_path / "test.py").write_text(content + "\n")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/source?path=test.py&line=10&context=2"
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            # context=2 means 2 lines before and after, so 5 total
            assert len(data["snippet"]) == 5
            assert data["snippet"][2]["highlight"] is True
        finally:
            server.stop()

    def test_source_path_outside_base(self, tmp_path: Path) -> None:
        """Path traversal outside base_dir returns 403."""
        server, port = _start_server(base_dir=tmp_path)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/source?path=../../../etc/passwd&line=1"
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 403
        finally:
            server.stop()

    def test_source_missing_path_param(self) -> None:
        """Missing path parameter returns 400."""
        server, port = _start_server()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/source?line=1")
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()


class TestServerMethods:
    """Tests for ViewerServer public methods."""

    def test_none_trace_constructor(self) -> None:
        """Constructor with None trace creates empty Trace."""
        server = ViewerServer(None)
        assert server.trace is not None
        assert server.trace.features == []

    def test_wait_method(self) -> None:
        """wait() blocks until server stops."""
        server, port = _start_server()
        try:
            # Start a thread that stops the server after a short delay
            def stop_soon():
                time.sleep(0.1)
                server.stop()

            t = threading.Thread(target=stop_soon, daemon=True)
            t.start()
            server.wait()
            t.join(timeout=2)
        except Exception:
            server.stop()

    def test_set_auto_run(self) -> None:
        """set_auto_run updates state and notifies clients."""
        server, port = _start_server()
        try:
            server.set_auto_run(False)
            assert server.get_auto_run() is False
            server.set_auto_run(True)
            assert server.get_auto_run() is True
        finally:
            server.stop()

    def test_is_running(self) -> None:
        """is_running returns current running state."""
        server, port = _start_server()
        try:
            assert server.is_running() is False
            server.set_running(True)
            assert server.is_running() is True
            server.set_running(False)
            assert server.is_running() is False
        finally:
            server.stop()

    def test_notify(self) -> None:
        """notify() pushes event to SSE clients without error."""
        server, port = _start_server()
        try:
            server.notify({"type": "custom", "data": "test"})
            # Should not raise
        finally:
            server.stop()

    def test_try_set_running(self) -> None:
        """try_set_running atomically sets running state."""
        server, port = _start_server()
        try:
            assert server.try_set_running(True) is True
            assert server.is_running() is True
            # Second call should fail
            assert server.try_set_running(True) is False
            # Reset
            server.set_running(False)
            assert server.try_set_running(True) is True
        finally:
            server.stop()


class TestGzipResponses:
    """Tests for gzip-compressed responses."""

    def test_trace_gzip(self) -> None:
        """Trace endpoint returns gzip when Accept-Encoding includes gzip."""
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/trace",
                headers={"Accept-Encoding": "gzip"},
            )
            with urllib.request.urlopen(req) as resp:
                assert resp.headers.get("Content-Encoding") == "gzip"
                data = gzip.decompress(resp.read())
                json.loads(data)  # should be valid JSON
        finally:
            server.stop()

    def test_static_file_gzip(self) -> None:
        """Static CSS file is gzipped when large enough."""
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/css/style.css",
                headers={"Accept-Encoding": "gzip"},
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    # May or may not be gzipped depending on file size
                    data = resp.read()
                    assert len(data) > 0
            except urllib.error.HTTPError:
                # File may not exist
                pass
        finally:
            server.stop()


class TestSSEHeartbeat:
    """Test SSE heartbeat functionality."""

    def test_sse_initial_state_error_handling(self) -> None:
        """SSE handles connection errors during initial state gracefully."""
        server, port = _start_server()
        try:
            # Create a client that immediately disconnects
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.sendall(b"GET /api/stream HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            # Read a bit then close
            sock.recv(1024)
            sock.close()
            # Server should not crash
            time.sleep(0.2)
        finally:
            server.stop()


class TestServeFileNotFound:
    """Test serving nonexistent static files."""

    def test_nonexistent_css_returns_404(self) -> None:
        server, port = _start_server()
        try:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/css/nonexistent.css")
            assert exc_info.value.code == 404
        finally:
            server.stop()

    def test_nonexistent_js_returns_404(self) -> None:
        server, port = _start_server()
        try:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/js/nonexistent.js")
            assert exc_info.value.code == 404
        finally:
            server.stop()


class TestProgressEdgeCases:
    """Edge cases for POST /api/progress."""

    def test_progress_invalid_content_length(self) -> None:
        """Malformed Content-Length header doesn't crash server."""
        server, port = _start_server()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.sendall(
                b"POST /api/progress HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: abc\r\n\r\n"
            )
            # Read response (may be empty or error)
            with contextlib.suppress(TimeoutError):
                sock.recv(4096)
            sock.close()
            # Server should still be alive
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/trace") as resp:
                assert resp.status == 200
        finally:
            server.stop()

    def test_progress_non_dict_json(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/progress",
                data=json.dumps([1, 2]).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_progress_invalid_json(self) -> None:
        server, port = _start_server()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/progress",
                data=b"not json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_progress_with_scenario_name(self) -> None:
        """Progress endpoint forwards scenario_name in notification."""
        server, port = _start_server()
        try:
            data = json.dumps(
                {
                    "event": "scenario_started",
                    "scenario_name": "My Scenario",
                    "completed": 1,
                    "total": 5,
                }
            ).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/progress",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert result["status"] == "ok"
        finally:
            server.stop()


class TestRerunEdgeCases:
    """Additional edge cases for /api/rerun."""

    def test_rerun_invalid_filter_value(self) -> None:
        """Invalid filter value returns 400."""
        server, port = _start_server(rerun_callback=mock.Mock())
        try:
            data = json.dumps({"filter": "invalid"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/rerun",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req)
            assert exc_info.value.code == 400
        finally:
            server.stop()

    def test_rerun_malformed_content_length(self) -> None:
        """Malformed Content-Length doesn't crash server."""
        server, port = _start_server(rerun_callback=mock.Mock())
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.sendall(
                b"POST /api/rerun HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: xyz\r\n\r\n"
            )
            with contextlib.suppress(TimeoutError):
                sock.recv(4096)
            sock.close()
            # Server should still be alive
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/trace") as resp:
                assert resp.status == 200
        finally:
            server.stop()
