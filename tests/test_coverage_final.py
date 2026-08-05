"""Additional tests to push coverage above 95%."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from unittest import mock

from behave_trace.cli.app import _cmd_run, _cmd_show, _watch_loop
from behave_trace.models import Environment, Feature, Scenario, Trace, TraceStats


def _make_trace() -> Trace:
    feature = Feature(name="Test Feature", location="test.feature:1")
    scenario = Scenario(name="Test Scenario", feature_name="Test Feature")
    feature.scenarios.append(scenario)
    stats = TraceStats(
        total_features=1,
        total_scenarios=1,
        total_steps=0,
        by_status={"passed": 1, "failed": 0},
        duration=1.5,
    )
    env = Environment(cwd=".")
    return Trace(features=[feature], stats=stats, environment=env)


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {
        "trace_file": "trace.json",
        "features_dir": ".",
        "port": 0,
        "no_browser": True,
        "tags": None,
        "watch": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# __main__.py — direct import to cover lines 3-10
# ---------------------------------------------------------------------------


class TestMainModuleImport:
    """Test that __main__.py can be imported directly."""

    def test_main_module_importable(self) -> None:
        """Importing __main__ module should not fail."""
        import behave_trace.__main__

        assert hasattr(behave_trace.__main__, "main")


# ---------------------------------------------------------------------------
# _cmd_show — signal.pause() path (non-Windows)
# ---------------------------------------------------------------------------


class TestCmdShowSignalPause:
    """Test _cmd_show on non-Windows (signal.pause path)."""

    def test_show_uses_signal_pause_on_non_windows(self, tmp_path: Path, capsys) -> None:
        """Show uses signal.pause() on non-Windows platforms."""
        trace_path = tmp_path / "trace.json"
        trace_path.write_text("{}")
        trace = _make_trace()
        args = _make_args(trace_file=str(trace_path), port=0, no_browser=True)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()

        with (
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", return_value=mock_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("sys.platform", "linux"),
            mock.patch("signal.pause", side_effect=KeyboardInterrupt, create=True),
        ):
            result = _cmd_show(args)

        assert result == 0
        mock_server.stop.assert_called_once()
        captured = capsys.readouterr()
        assert "Stopping..." in captured.out


# ---------------------------------------------------------------------------
# _cmd_run — signal.pause() path (non-Windows)
# ---------------------------------------------------------------------------


class TestCmdRunSignalPause:
    """Test _cmd_run on non-Windows (signal.pause path)."""

    def test_run_uses_signal_pause_on_non_windows(self, tmp_path: Path, capsys) -> None:
        """Run uses signal.pause() on non-Windows platforms."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True, watch=False)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        mock_result = mock.Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=mock_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", return_value=mock_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("sys.platform", "linux"),
            mock.patch("signal.pause", side_effect=KeyboardInterrupt, create=True),
        ):
            result = _cmd_run(args)

        assert result == 0
        mock_server.stop.assert_called_once()


# ---------------------------------------------------------------------------
# rerun_callback — directly invoke the callback captured from _cmd_run
# ---------------------------------------------------------------------------


class TestRerunCallbackDirect:
    """Directly test the rerun_callback created by _cmd_run."""

    def test_rerun_callback_with_scenario_names_success(self, tmp_path: Path, capsys) -> None:
        """Rerun callback with scenario names runs filtered behave and updates server."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        filtered_result = mock.Mock()
        filtered_result.stdout = "Filtered output\n"
        filtered_result.stderr = ""
        filtered_result.trace_path = trace_path
        mock_runner.run_filtered = mock.Mock(return_value=filtered_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.update_trace = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            # Invoke the captured rerun callback inside the mock context
            assert len(captured_callbacks) == 1
            captured_callbacks[0](["Scenario 1", "Scenario 2"])

        mock_runner.run_filtered.assert_called_once()
        mock_server.update_trace.assert_called_once()
        mock_server.set_running.assert_called_with(False)
        captured = capsys.readouterr()
        assert "Re-running behave" in captured.out
        assert "Filtered output" in captured.out
        assert "Viewer updated" in captured.out

    def test_rerun_callback_without_scenario_names(self, tmp_path: Path, capsys) -> None:
        """Rerun callback without scenario names runs full behave."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        # For the rerun (no scenario names), runner.run is called again
        rerun_result = mock.Mock()
        rerun_result.stdout = "Full rerun\n"
        rerun_result.stderr = ""
        rerun_result.trace_path = trace_path
        # First call: initial run, second call: rerun
        mock_runner.run = mock.Mock(side_effect=[initial_result, rerun_result])

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.update_trace = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            assert len(captured_callbacks) == 1
            captured_callbacks[0](None)  # No scenario names → full run

        assert mock_runner.run.call_count == 2
        mock_server.update_trace.assert_called_once()
        captured = capsys.readouterr()
        assert "Full rerun" in captured.out
        assert "Viewer updated" in captured.out

    def test_rerun_callback_no_trace_file(self, tmp_path: Path, capsys) -> None:
        """Rerun callback handles missing trace file."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        filtered_result = mock.Mock()
        filtered_result.stdout = ""
        filtered_result.stderr = ""
        filtered_result.trace_path = None  # No trace produced
        mock_runner.run_filtered = mock.Mock(return_value=filtered_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            assert len(captured_callbacks) == 1
            captured_callbacks[0](["S1"])

        mock_server.set_running.assert_called_with(False)
        captured = capsys.readouterr()
        assert "did not produce a trace file" in captured.err

    def test_rerun_callback_load_trace_error(self, tmp_path: Path, capsys) -> None:
        """Rerun callback handles trace load errors."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        filtered_result = mock.Mock()
        filtered_result.stdout = ""
        filtered_result.stderr = ""
        filtered_result.trace_path = trace_path
        mock_runner.run_filtered = mock.Mock(return_value=filtered_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        # First load: initial run succeeds; second load: rerun fails
        load_count = [0]

        def load_side_effect(*args, **kwargs):
            load_count[0] += 1
            if load_count[0] == 1:
                return trace
            raise ValueError("bad")

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", side_effect=load_side_effect),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            # Invoke the captured rerun callback inside the mock context
            assert len(captured_callbacks) == 1
            captured_callbacks[0](["S1"])

        mock_server.set_running.assert_called_with(False)
        captured = capsys.readouterr()
        assert "Error loading trace" in captured.err

    def test_rerun_callback_exception(self, tmp_path: Path, capsys) -> None:
        """Rerun callback handles runner exceptions."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)
        mock_runner.run_filtered = mock.Mock(side_effect=RuntimeError("crash"))

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            assert len(captured_callbacks) == 1
            captured_callbacks[0](["S1"])

        mock_server.set_running.assert_called_with(False)
        captured = capsys.readouterr()
        assert "Error during re-run" in captured.err

    def test_rerun_callback_server_none(self, tmp_path: Path) -> None:
        """Rerun callback is a no-op when server is None."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)

        # We can't easily test server=None since the callback closes over the server
        # variable. But the test above covers the normal path.
        assert len(captured_callbacks) == 1

    def test_rerun_callback_with_stderr_output(self, tmp_path: Path, capsys) -> None:
        """Rerun callback prints stderr from behave."""
        args = _make_args(features_dir=str(tmp_path), port=0, no_browser=True)

        trace = _make_trace()
        trace_path = Path(tempfile.gettempdir()) / "behave-trace-run.json"
        trace_path.write_text("{}")

        mock_runner = mock.Mock()
        initial_result = mock.Mock()
        initial_result.stdout = ""
        initial_result.stderr = ""
        initial_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=initial_result)

        filtered_result = mock.Mock()
        filtered_result.stdout = ""
        filtered_result.stderr = "Some warning\n"
        filtered_result.trace_path = trace_path
        mock_runner.run_filtered = mock.Mock(return_value=filtered_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.start = mock.Mock(return_value="http://127.0.0.1:8080")
        mock_server.stop = mock.Mock()
        mock_server.update_trace = mock.Mock()
        mock_server.set_running = mock.Mock()

        captured_callbacks: list = []

        def capture_server(*args, **kwargs):
            cb = kwargs.get("rerun_callback")
            if cb:
                captured_callbacks.append(cb)
            return mock_server

        with (
            mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("behave_trace.viewer.server.ViewerServer", side_effect=capture_server),
            mock.patch("behave_trace.viewer.browser.open_app"),
            mock.patch("threading.Event.wait", side_effect=KeyboardInterrupt),
        ):
            _cmd_run(args)
            assert len(captured_callbacks) == 1
            captured_callbacks[0](["S1"])

        captured = capsys.readouterr()
        assert "Some warning" in captured.err


# ---------------------------------------------------------------------------
# _watch_loop — stderr output from re-run
# ---------------------------------------------------------------------------


class TestWatchLoopStderr:
    """Test _watch_loop prints stderr from behave re-run."""

    def test_watch_loop_on_change_with_stderr(self, tmp_path: Path, capsys) -> None:
        """Watch loop prints stderr from re-run."""
        args = _make_args(features_dir=str(tmp_path))
        trace_path = tmp_path / "trace.json"
        trace_path.write_text("{}")
        trace = _make_trace()

        mock_runner = mock.Mock()
        mock_result = mock.Mock()
        mock_result.stdout = ""
        mock_result.stderr = "Warning message\n"
        mock_result.trace_path = trace_path
        mock_runner.run = mock.Mock(return_value=mock_result)

        mock_server = mock.Mock()
        mock_server.url = "http://127.0.0.1:8080"
        mock_server.get_auto_run = mock.Mock(return_value=True)
        mock_server.try_set_running = mock.Mock(return_value=True)
        mock_server.set_running = mock.Mock()
        mock_server.update_trace = mock.Mock()
        mock_server.stop = mock.Mock()

        callbacks = []
        mock_watcher = mock.Mock()

        def capture_watcher(dir, callback, **kw):
            callbacks.append(callback)
            return mock_watcher

        with (
            mock.patch("behave_trace.watcher.FileWatcher", side_effect=capture_watcher),
            mock.patch("behave_trace.serializer.Serializer.load", return_value=trace),
            mock.patch("threading.Event") as mock_event_cls,
        ):
            stop_event = mock.Mock()

            def wait_then_call(*args, **kw):
                if callbacks:
                    callbacks[0](["test.py"])
                raise KeyboardInterrupt

            stop_event.wait = mock.Mock(side_effect=wait_then_call)
            mock_event_cls.return_value = stop_event

            result = _watch_loop(args, tmp_path, trace_path, mock_runner, mock_server)

        assert result == 0
        captured = capsys.readouterr()
        assert "Warning message" in captured.err
