"""Local web server for the trace viewer.

Uses stdlib http.server — no external dependencies.
Serves static assets (HTML/CSS/JS), the trace JSON endpoint, a source
code endpoint, an SSE streaming endpoint for live updates, and a watch-mode
status endpoint.
Gzip compression for large traces.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import queue
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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

_SOURCE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".feature": "gherkin",
}

_DEFAULT_CONTEXT_LINES = 5

_SSE_HEARTBEAT_S = 15.0


class _ServerState:
    """Mutable state shared between the server and request handlers."""

    def __init__(
        self,
        trace_json: bytes,
        watching: bool,
        can_run: bool = False,
        auto_run: bool = False,
    ) -> None:
        self.trace_bytes: bytes = trace_json
        self.trace_gzipped: bytes = gzip.compress(trace_json)
        self.watching: bool = watching
        self.can_run: bool = can_run
        self.auto_run: bool = auto_run
        self.running: bool = False
        self.progress: dict[str, int] = {"completed": 0, "total": 0}
        self.progress_start: float | None = None
        self.sse_clients: list[queue.Queue[dict[str, Any]]] = []
        self.clients_lock = threading.Lock()

    def notify(self, event: dict[str, Any]) -> None:
        """Push an event to all connected SSE clients."""
        with self.clients_lock:
            for q in self.sse_clients:
                with contextlib.suppress(queue.Full):
                    q.put_nowait(event)

    def update_trace(self, trace_json: bytes) -> None:
        """Update the trace data and notify clients to re-fetch."""
        self.trace_bytes = trace_json
        self.trace_gzipped = gzip.compress(trace_json)
        self.notify({"type": "trace_updated"})

    def set_running(self, running: bool) -> None:
        """Set the running state and notify clients."""
        self.running = running
        if running:
            self.progress = {"completed": 0, "total": 0}
            self.progress_start = time.time()
            self.notify({"type": "run_started", "progressStart": self.progress_start})
        else:
            self.progress_start = None
            self.notify({"type": "run_completed"})


class ViewerServer:
    """Serve the trace viewer SPA and trace data on localhost.

    Args:
        trace: The :class:`Trace` object to visualize.
        port: Port to bind (0 = auto-select a free port).
        watching: Whether the server is in watch mode (enables SSE and
            run-status endpoints).
        rerun_callback: Optional callback invoked when the client POSTs
            to ``/api/rerun``. Receives a list of scenario names or None.

    Example:
        >>> server = ViewerServer(trace, port=8080)
        >>> server.start()
        'http://127.0.0.1:8080'
        >>> server.stop()
    """

    def __init__(
        self,
        trace: Trace | None = None,
        port: int = 0,
        watching: bool = False,
        rerun_callback: Callable[[list[str] | None], None] | None = None,
    ) -> None:
        if trace is None:
            from behave_trace.models import Trace as _Trace

            trace = _Trace()
        self.trace = trace
        self.port = port
        self.watching = watching
        self.rerun_callback = rerun_callback
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._trace_json: bytes = json.dumps(as_dict(self.trace), default=str).encode()
        self._base_dir: Path = Path(trace.environment.cwd or ".").resolve()
        self._state = _ServerState(
            self._trace_json,
            watching,
            can_run=rerun_callback is not None,
            auto_run=watching,
        )

    @property
    def url(self) -> str:
        """Return the URL the server is listening on."""
        actual_port = self._httpd.server_address[1] if self._httpd is not None else self.port
        return f"http://127.0.0.1:{actual_port}"

    def start(self) -> str:
        """Start the server and return the URL."""
        state = self._state
        base_dir = self._base_dir
        rerun_cb = self.rerun_callback

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/api/trace":
                    self._send_json(state.trace_bytes, state.trace_gzipped)
                elif parsed.path == "/api/source":
                    self._serve_source(parsed.query, base_dir)
                elif parsed.path == "/api/watching":
                    payload = json.dumps({"watching": state.watching}).encode()
                    self._send_json(payload, gzip.compress(payload))
                elif parsed.path == "/api/stream":
                    self._handle_sse(state)
                elif parsed.path == "/":
                    self._serve_file(_ASSETS_DIR / "index.html")
                elif parsed.path.startswith("/css/") or parsed.path.startswith("/js/"):
                    self._serve_path(parsed.path.lstrip("/"))
                else:
                    self.send_error(404)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/api/rerun":
                    self._handle_rerun(state, rerun_cb)
                elif parsed.path == "/api/run":
                    self._handle_run(state, rerun_cb)
                elif parsed.path == "/api/autorun":
                    self._handle_autorun(state)
                elif parsed.path == "/api/progress":
                    self._handle_progress(state)
                else:
                    self._send_json_response({"error": "Not found"}, status=404)

            def _handle_progress(self, sstate: _ServerState) -> None:
                """Handle POST /api/progress — update live progress."""
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                except (ValueError, TypeError):
                    content_length = 0
                body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._send_json_response({"error": "Invalid JSON"}, status=400)
                    return

                if not isinstance(payload, dict):
                    self._send_json_response({"error": "Expected JSON object"}, status=400)
                    return

                completed = payload.get("completed", sstate.progress["completed"])
                total = payload.get("total", sstate.progress["total"])
                sstate.progress = {
                    "completed": int(completed),
                    "total": int(total),
                }
                sstate.notify({
                    "type": "scenario_completed",
                    "completed": sstate.progress["completed"],
                    "total": sstate.progress["total"],
                    "scenario_name": payload.get("scenario_name", ""),
                })
                self._send_json_response({"status": "ok"})

            def _handle_autorun(self, sstate: _ServerState) -> None:
                """Handle POST /api/autorun — toggle auto-run on/off."""
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                except (ValueError, TypeError):
                    content_length = 0
                body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._send_json_response({"error": "Invalid JSON"}, status=400)
                    return

                if not isinstance(payload, dict):
                    self._send_json_response({"error": "Expected JSON object"}, status=400)
                    return

                enabled = payload.get("enabled")
                if not isinstance(enabled, bool):
                    self._send_json_response({"error": "Missing 'enabled' boolean"}, status=400)
                    return

                sstate.auto_run = enabled
                sstate.notify({"type": "state", "autoRun": enabled})
                self._send_json_response({"status": "ok", "autoRun": enabled})

            def _handle_run(
                self,
                sstate: _ServerState,
                cb: Callable[[list[str] | None], None] | None,
            ) -> None:
                """Handle POST /api/run — execute behave from scratch (all tests)."""
                if cb is None:
                    self._send_json_response(
                        {"error": "Run not available (no callback configured)"},
                        status=501,
                    )
                    return
                if sstate.running:
                    self._send_json_response({"error": "Already running"}, status=409)
                    return
                self._send_json_response({"status": "accepted"})
                thread = threading.Thread(target=cb, args=(None,), daemon=True)
                thread.start()

            def _handle_rerun(
                self,
                sstate: _ServerState,
                cb: Callable[[list[str] | None], None] | None,
            ) -> None:
                """Handle POST /api/rerun — re-execute behave with optional filter."""
                if cb is None:
                    self._send_json_response(
                        {"error": "Re-run not available (no callback configured)"},
                        status=501,
                    )
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                except (ValueError, TypeError):
                    content_length = 0
                body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._send_json_response({"error": "Invalid JSON"}, status=400)
                    return

                if not isinstance(payload, dict):
                    self._send_json_response({"error": "Expected JSON object"}, status=400)
                    return

                filter_type = payload.get("filter", "all")
                scenarios = payload.get("scenarios")

                if filter_type not in ("failed", "all"):
                    self._send_json_response(
                        {"error": "Invalid filter; must be 'failed' or 'all'"},
                        status=400,
                    )
                    return

                scenario_names: list[str] | None = None
                if filter_type == "failed" and isinstance(scenarios, list):
                    scenario_names = [str(s) for s in scenarios if s]

                # Respond immediately; the callback runs in a thread
                self._send_json_response({"status": "accepted"})

                # Run the callback in a background thread so we don't block
                thread = threading.Thread(target=cb, args=(scenario_names,), daemon=True)
                thread.start()

            def _handle_sse(self, sstate: _ServerState) -> None:
                """Handle an SSE connection — streams events to the client."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                client_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=64)
                with sstate.clients_lock:
                    sstate.sse_clients.append(client_queue)

                # Send initial state
                initial = {
                    "type": "state",
                    "running": sstate.running,
                    "watching": sstate.watching,
                    "canRun": sstate.can_run,
                    "autoRun": sstate.auto_run,
                    "progress": sstate.progress,
                    "progressStart": sstate.progress_start,
                }
                try:
                    self._sse_send(initial)
                except ConnectionError:
                    with sstate.clients_lock:
                        if client_queue in sstate.sse_clients:
                            sstate.sse_clients.remove(client_queue)
                    return

                try:
                    while True:
                        try:
                            event = client_queue.get(timeout=_SSE_HEARTBEAT_S)
                            self._sse_send(event)
                        except queue.Empty:
                            # Send heartbeat to keep connection alive
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                except ConnectionError:
                    pass
                finally:
                    with sstate.clients_lock:
                        if client_queue in sstate.sse_clients:
                            sstate.sse_clients.remove(client_queue)

            def _sse_send(self, event: dict[str, Any]) -> None:
                """Send a single SSE event."""
                data = f"data: {json.dumps(event)}\n\n"
                self.wfile.write(data.encode())
                self.wfile.flush()

            def _serve_path(self, relative: str) -> None:
                """Serve a file from assets dir with path-traversal protection."""
                target = (_ASSETS_DIR / relative).resolve()
                try:
                    target.relative_to(_ASSETS_DIR.resolve())
                except ValueError:
                    self.send_error(404)
                    return
                self._serve_file(target)

            def _serve_source(self, query: str, base: Path) -> None:
                """Serve a source code snippet around a given line.

                Query params:
                    path:    relative file path (e.g. "steps/calculator.py")
                    line:    line number to center the snippet on
                    context: number of context lines before/after (default 5)
                """
                params = parse_qs(query)
                file_path = params.get("path", [""])[0]
                line_str = params.get("line", ["0"])[0]
                context_str = params.get("context", [str(_DEFAULT_CONTEXT_LINES)])[0]

                if not file_path:
                    self._send_json_response({"error": "Missing 'path' parameter"}, status=400)
                    return

                try:
                    line = int(line_str)
                    context = max(0, int(context_str))
                except ValueError:
                    self._send_json_response(
                        {"error": "Invalid 'line' or 'context' parameter"}, status=400
                    )
                    return

                # Resolve path relative to base_dir with traversal protection
                candidate = (base / file_path).resolve()
                try:
                    candidate.relative_to(base)
                except ValueError:
                    self._send_json_response({"error": "Path outside base directory"}, status=403)
                    return

                if not candidate.exists() or not candidate.is_file():
                    self._send_json_response({"error": f"File not found: {file_path}"}, status=404)
                    return

                try:
                    lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError as exc:
                    self._send_json_response({"error": f"Cannot read file: {exc}"}, status=500)
                    return

                total_lines = len(lines)
                # Clamp line to valid range (1-indexed in the location)
                target_line = max(1, min(line, total_lines))
                start = max(0, target_line - 1 - context)
                end = min(total_lines, target_line + context)

                snippet_lines: list[dict[str, Any]] = []
                for i in range(start, end):
                    snippet_lines.append(
                        {
                            "number": i + 1,
                            "content": lines[i],
                            "highlight": (i + 1) == target_line,
                        }
                    )

                language = _SOURCE_EXTENSIONS.get(candidate.suffix, "text")

                payload = {
                    "path": file_path,
                    "line": target_line,
                    "language": language,
                    "snippet": snippet_lines,
                    "total_lines": total_lines,
                }
                self._send_json_response(payload)

            def _send_json_response(self, data: dict[str, Any], status: int = 200) -> None:
                """Send a JSON response with optional gzip."""
                body = json.dumps(data).encode()
                accept_gzip = "gzip" in (self.headers.get("Accept-Encoding", ""))
                if accept_gzip and len(body) > _GZIP_THRESHOLD:
                    body = gzip.compress(body)
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

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

    def update_trace(self, trace: Trace) -> None:
        """Update the trace served by this server and notify SSE clients."""
        self.trace = trace
        trace_json = json.dumps(as_dict(trace), default=str).encode()
        self._state.update_trace(trace_json)

    def set_running(self, running: bool) -> None:
        """Set the running state and notify SSE clients."""
        self._state.set_running(running)

    def set_auto_run(self, auto_run: bool) -> None:
        """Set the auto-run state and notify SSE clients."""
        self._state.auto_run = auto_run
        self._state.notify({"type": "state", "autoRun": auto_run})

    def get_auto_run(self) -> bool:
        """Return the current auto-run state."""
        return self._state.auto_run

    def notify(self, event: dict[str, Any]) -> None:
        """Push a custom event to all SSE clients."""
        self._state.notify(event)
