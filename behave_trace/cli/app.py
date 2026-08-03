"""CLI for behave-trace.

Usage::

    behave-trace show trace.json [--port PORT] [--no-browser]
    behave-trace --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from behave_trace import __version__
from behave_trace.utils import format_duration


def _cmd_show(args: argparse.Namespace) -> int:
    """Load a trace file, start the viewer server, and open the browser."""
    from behave_trace.serializer import Serializer
    from behave_trace.viewer.browser import open_app
    from behave_trace.viewer.server import ViewerServer

    trace_path = Path(args.trace_file)
    if not trace_path.exists():
        print(f"Error: trace file not found: {trace_path}", file=sys.stderr)
        return 1

    try:
        trace = Serializer.load(trace_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error loading trace: {exc}", file=sys.stderr)
        return 1

    # Print summary
    stats = trace.stats
    passed = stats.by_status.get("passed", 0)
    failed = stats.by_status.get("failed", 0)
    print(f"Trace: {trace_path}")
    print(f"Features: {stats.total_features}")
    print(f"Scenarios: {stats.total_scenarios} ({passed} passed, {failed} failed)")
    print(f"Steps: {stats.total_steps}")
    print(f"Duration: {format_duration(stats.duration)}")

    # Start server
    try:
        server = ViewerServer(trace, port=args.port)
        server.start()
    except OSError as exc:
        print(f"Error: cannot start server on port {args.port}: {exc}", file=sys.stderr)
        if args.port != 0:
            print("Try a different port with --port, or use --port 0 for auto.", file=sys.stderr)
        return 1

    url = server.url
    print(f"\nViewer running at {url}")
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        open_app(url)

    # Block until Ctrl+C — cross-platform
    try:
        if sys.platform == "win32":
            import threading

            threading.Event().wait()
        else:
            import signal

            signal.pause()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.stop()

    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the behave-trace CLI."""
    parser = argparse.ArgumentParser(
        prog="behave-trace",
        description="Trace viewer for Behave BDD tests.",
    )
    parser.add_argument("--version", action="version", version=f"behave-trace {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    show_parser = subparsers.add_parser("show", help="Open the trace viewer for a .trace file.")
    show_parser.add_argument("trace_file", help="Path to the .trace file to visualize.")
    show_parser.add_argument(
        "--port", type=int, default=0, help="Port to run the viewer on (0 = auto)."
    )
    show_parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser window."
    )

    args = parser.parse_args(argv)

    if args.command == "show":
        return _cmd_show(args)

    parser.print_help()
    return 0
