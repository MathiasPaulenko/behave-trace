"""Local web server for the trace viewer.

Uses stdlib http.server — no external dependencies.
Serves static assets (HTML/CSS/JS) and the trace JSON endpoint.
Gzip compression for large traces.
"""

from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from behave_trace.models import Trace, as_dict

_ASSETS_DIR = Path(__file__).parent.parent / "assets"

_MIME_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

_GZIP_THRESHOLD = 1024  # only compress responses > 1KB

_COMPRESSIBLE_TYPES = frozenset(
    {
        "text/html; charset=utf-8",
        "text/css; charset=utf-8",
        "application/javascript; charset=utf-8",
        "application/json; charset=utf-8",
    }
)


class ViewerServer:
    """Serve the trace viewer SPA and trace data on localhost."""

    def __init__(self, trace: Trace, port: int = 0) -> None:
        self.trace = trace
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._trace_json: bytes = json.dumps(as_dict(self.trace), default=str).encode()

    @property
    def url(self) -> str:
        """Return the URL the server is listening on."""
        actual_port = self._httpd.server_address[1] if self._httpd is not None else self.port
        return f"http://127.0.0.1:{actual_port}"

    def start(self) -> str:
        """Start the server and return the URL."""
        trace_bytes = self._trace_json
        trace_gzipped = gzip.compress(trace_bytes)

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                if self.path == "/api/trace":
                    self._send_json(trace_bytes, trace_gzipped)
                elif self.path == "/":
                    self._serve_file(_ASSETS_DIR / "index.html")
                elif self.path.startswith("/css/") or self.path.startswith("/js/"):
                    self._serve_path(self.path.lstrip("/"))
                else:
                    self.send_error(404)

            def _serve_path(self, relative: str) -> None:
                """Serve a file from assets dir with path-traversal protection."""
                target = (_ASSETS_DIR / relative).resolve()
                try:
                    target.relative_to(_ASSETS_DIR.resolve())
                except ValueError:
                    self.send_error(404)
                    return
                self._serve_file(target)

            def _send_json(self, raw: bytes, gzipped: bytes) -> None:
                accept_gzip = "gzip" in (self.headers.get("Accept-Encoding", ""))
                body = gzipped if accept_gzip else raw
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                if accept_gzip:
                    self.send_header("Content-Encoding", "gzip")
                self.end_headers()
                self.wfile.write(body)

            def _serve_file(self, path: Path) -> None:
                if not path.exists() or not path.is_file():
                    self.send_error(404)
                    return
                mime = _MIME_TYPES.get(path.suffix, "application/octet-stream")
                data = path.read_bytes()
                if mime in _COMPRESSIBLE_TYPES:
                    accept_gzip = "gzip" in (self.headers.get("Accept-Encoding", ""))
                    if accept_gzip and len(data) > _GZIP_THRESHOLD:
                        data = gzip.compress(data)
                        self.send_response(200)
                        self.send_header("Content-Type", mime)
                        self.send_header("Content-Encoding", "gzip")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        actual_port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{actual_port}"

    def wait(self) -> None:
        """Block until the server stops."""
        if self._thread is not None:
            self._thread.join()

    def stop(self) -> None:
        """Stop the server."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
