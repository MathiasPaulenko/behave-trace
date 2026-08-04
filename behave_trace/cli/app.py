"""CLI for behave-trace.

Usage::

    behave-trace show trace.json [--port PORT] [--no-browser]
    behave-trace run [features_dir] [--port PORT] [--no-browser] [--tags TAGS]
    behave-trace --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from behave_trace import __version__
from behave_trace.utils import format_duration


def _resolve_features(dir_path: Path) -> tuple[Path | None, str | Path]:
    """Return (cwd, features_arg) for behave subprocess.

    If the user passed a directory containing a ``features/`` subfolder
    (typical for example projects with a ``behave.ini`` in the root),
    run behave from that root so the configuration is discovered.
    """
    if dir_path.name == "features":
        return dir_path.parent, "features"
    if (dir_path / "features").is_dir():
        return dir_path, "features"
    return None, dir_path


if TYPE_CHECKING:
    from behave_trace.models import Trace
    from behave_trace.runner import BehaveRunner
    from behave_trace.viewer.server import ViewerServer


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


def _cmd_run(args: argparse.Namespace) -> int:
    """Run behave with the trace formatter, then open the viewer."""
    from behave_trace.runner import BehaveRunner
    from behave_trace.serializer import Serializer
    from behave_trace.viewer.browser import open_app
    from behave_trace.viewer.server import ViewerServer

    features_dir = Path(args.features_dir)
    if not features_dir.exists():
        print(f"Error: features directory not found: {features_dir}", file=sys.stderr)
        return 1

    import tempfile

    trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
    runner = BehaveRunner()

    def run_behave() -> int:
        """Execute behave and print output. Returns 0 on success."""
        print(f"Running behave in {features_dir}...")
        run_cwd, run_features = _resolve_features(features_dir)
        try:
            result = runner.run(
                features_dir=run_features,
                output_path=trace_path,
                tags=args.tags,
                cwd=run_cwd,
            )
        except Exception as exc:
            print(f"Error: failed to run behave: {exc}", file=sys.stderr)
            return 1
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.trace_path is None or not result.trace_path.exists():
            print("Error: behave did not produce a trace file.", file=sys.stderr)
            return 1
        return 0

    # Initial run
    if run_behave() != 0:
        if not args.watch:
            print("Initial run failed. Starting viewer with empty trace...", file=sys.stderr)
        else:
            print("Waiting for file changes to re-run...", file=sys.stderr)

    # Load trace
    try:
        trace = Serializer.load(trace_path)
    except Exception as exc:
        print(f"Error loading trace: {exc}", file=sys.stderr)
        trace = None

    # Print summary
    if trace is not None:
        _print_summary(trace, trace_path)

    # Rerun callback for POST /api/rerun
    def rerun_callback(scenario_names: list[str] | None) -> None:
        """Re-execute behave (optionally filtered) and update the server."""
        if server is None:
            return

        server.set_running(True)

        run_cwd, run_features = _resolve_features(features_dir)

        try:
            print("Re-running behave...")
            if scenario_names:
                result = runner.run_filtered(
                    features_dir=run_features,
                    output_path=trace_path,
                    tags=args.tags,
                    scenario_names=scenario_names,
                    cwd=run_cwd,
                    server_url=server.url,
                )
            else:
                result = runner.run(
                    features_dir=run_features,
                    output_path=trace_path,
                    tags=args.tags,
                    cwd=run_cwd,
                    server_url=server.url,
                )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

            if result.trace_path is None or not result.trace_path.exists():
                print("Error: behave did not produce a trace file.", file=sys.stderr)
                return

            try:
                new_trace = Serializer.load(result.trace_path)
            except Exception as exc:
                print(f"Error loading trace: {exc}", file=sys.stderr)
                return

            _print_summary(new_trace, result.trace_path)

            if server is not None:
                server.update_trace(new_trace)

            print("Viewer updated.")
        except Exception as exc:
            print(f"Error during re-run: {exc}", file=sys.stderr)
        finally:
            server.set_running(False)

    # Start server (even without trace — enables "Run all" from UI)
    server = None
    try:
        server = ViewerServer(
            trace,
            port=args.port,
            watching=args.watch,
            rerun_callback=rerun_callback,
        )
        server.start()
    except OSError as exc:
        print(f"Error: cannot start server on port {args.port}: {exc}", file=sys.stderr)
        if args.port != 0:
            print("Try a different port with --port, or use --port 0 for auto.", file=sys.stderr)
        return 1

    if server is not None:
        url = server.url
        print(f"\nViewer running at {url}")
        if args.watch:
            print("Watching for changes... Press Ctrl+C to stop.")
        else:
            print("Press Ctrl+C to stop.")

        if not args.no_browser:
            open_app(url)

    # Watch mode: re-run on file changes
    if args.watch:
        return _watch_loop(args, features_dir, trace_path, runner, server)

    # Non-watch: block until Ctrl+C
    if server is not None:
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


def _print_summary(trace: Trace, trace_path: Path) -> None:
    """Print trace summary to stdout."""
    stats = trace.stats
    passed = stats.by_status.get("passed", 0)
    failed = stats.by_status.get("failed", 0)
    print(f"\nTrace: {trace_path}")
    print(f"Features: {stats.total_features}")
    print(f"Scenarios: {stats.total_scenarios} ({passed} passed, {failed} failed)")
    print(f"Steps: {stats.total_steps}")
    print(f"Duration: {format_duration(stats.duration)}")


def _watch_loop(
    args: argparse.Namespace,
    features_dir: Path,
    trace_path: Path,
    runner: BehaveRunner,
    server: ViewerServer | None,
) -> int:
    """Run the watch loop, re-executing behave on file changes."""
    import threading

    from behave_trace.serializer import Serializer
    from behave_trace.watcher import FileWatcher

    stop_event = threading.Event()

    def on_change(changed_files: list[str]) -> None:
        print(f"\nFiles changed: {', '.join(changed_files)}")

        if server is None:
            return

        if not server.get_auto_run():
            print("Auto-run is disabled; ignoring file changes.")
            return

        print("Re-running behave...")

        server.set_running(True)

        try:
            # Re-run behave
            run_cwd, run_features = _resolve_features(features_dir)
            result = runner.run(
                features_dir=run_features,
                output_path=trace_path,
                tags=args.tags,
                cwd=run_cwd,
                server_url=server.url,
            )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

            if result.trace_path is None or not result.trace_path.exists():
                print("Error: behave did not produce a trace file.", file=sys.stderr)
                return

            # Reload trace
            try:
                new_trace = Serializer.load(result.trace_path)
            except Exception as exc:
                print(f"Error loading trace: {exc}", file=sys.stderr)
                return

            _print_summary(new_trace, result.trace_path)

            # Update the server's trace in-place (no restart needed)
            if server is not None:
                server.update_trace(new_trace)

            print("Viewer updated.")
        except Exception as exc:
            print(f"Error during watch re-run: {exc}", file=sys.stderr)
        finally:
            if server is not None:
                server.set_running(False)

    watcher = FileWatcher(features_dir, on_change, debounce_ms=500)
    watcher.start()
    print(f"Watching {features_dir} for changes...")

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        watcher.stop()
        if server is not None:
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

    run_parser = subparsers.add_parser(
        "run", help="Run behave with the trace formatter and open the viewer."
    )
    run_parser.add_argument(
        "features_dir", nargs="?", default=".", help="Directory containing .feature files."
    )
    run_parser.add_argument(
        "--port", type=int, default=0, help="Port to run the viewer on (0 = auto)."
    )
    run_parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser window."
    )
    run_parser.add_argument(
        "--tags", default=None, help="Tag expression to pass to behave (e.g. @smoke)."
    )
    run_parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for file changes and re-run tests automatically.",
    )

    args = parser.parse_args(argv)

    if args.command == "show":
        return _cmd_show(args)
    if args.command == "run":
        return _cmd_run(args)

    parser.print_help()
    return 0
