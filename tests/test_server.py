"""Tests for behave_trace.viewer.server."""

from __future__ import annotations

import gzip
import json
import urllib.request

import pytest

from behave_trace.models import STATUS_PASSED, Feature, Scenario, Step, Trace, TraceStats
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
