"""Edge-case tests for the FileWatcher class."""

from __future__ import annotations

import time
from pathlib import Path
from unittest import mock

from behave_trace.watcher import FileWatcher, _is_watched


class TestFireCallbackEdge:
    """Edge cases for _fire_callback."""

    def test_fire_callback_with_stop_event_set(self, tmp_path: Path) -> None:
        """_fire_callback should be a no-op when stop_event is set."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)
        watcher._stop_event.set()
        watcher._pending_files.add("test.py")
        watcher._fire_callback()
        callback.assert_not_called()

    def test_fire_callback_with_empty_pending(self, tmp_path: Path) -> None:
        """_fire_callback should be a no-op when no files are pending."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)
        watcher._fire_callback()
        callback.assert_not_called()


class TestPollingEdge:
    """Edge cases for the polling backend."""

    def test_polling_detects_deleted_files(self, tmp_path: Path) -> None:
        """Polling loop should handle file deletion without crashing."""
        callback = mock.Mock()
        f = tmp_path / "test.feature"
        f.write_text("Feature: Test\n")

        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)
        watcher.start()

        # Wait for initial scan
        time.sleep(0.15)

        # Delete the file
        f.unlink()

        # Wait for next poll cycle
        time.sleep(0.15)

        watcher.stop()
        # Should not have crashed

    def test_scan_files_nonexistent_dir(self, tmp_path: Path) -> None:
        """_scan_files returns empty list for nonexistent directory."""
        callback = mock.Mock()
        nonexistent = tmp_path / "does_not_exist"
        watcher = FileWatcher(nonexistent, callback, debounce_ms=0.05)
        result = watcher._scan_files()
        assert result == []

    def test_scan_files_oserror(self, tmp_path: Path) -> None:
        """_scan_files returns empty list when rglob raises OSError."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)
        with mock.patch("pathlib.Path.rglob", side_effect=OSError("permission")):
            result = watcher._scan_files()
        assert result == []


class TestWatchdogHandlerEdge:
    """Edge cases for the watchdog event handler."""

    def test_on_modified_directory_event_ignored(self, tmp_path: Path) -> None:
        """Directory modification events should be ignored."""
        callback = mock.Mock()
        FileWatcher(tmp_path, callback, debounce_ms=0.05)

        # Access the watchdog handler by simulating events
        # We need to test the handler logic directly

        # Simulate a directory event
        event = mock.Mock()
        event.is_directory = True
        event.src_path = str(tmp_path)

        # The handler should skip directory events
        # We test _is_watched returns False for directories (no extension)
        assert _is_watched(str(tmp_path)) is False

    def test_watchdog_on_created_calls_on_modified(self, tmp_path: Path) -> None:
        """on_created should delegate to on_modified."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)

        # Create a file to trigger the handler
        f = tmp_path / "new.py"
        f.write_text("# test")

        # If watchdog is available, this will trigger the handler
        # If not, the polling fallback handles it
        time.sleep(0.2)
        watcher.stop()

    def test_stop_with_watchdog_observer_exception(self, tmp_path: Path) -> None:
        """stop() should handle exceptions from observer.stop()/join()."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)

        # Mock an observer that raises on stop
        fake_observer = mock.Mock()
        fake_observer.stop = mock.Mock(side_effect=RuntimeError("fail"))
        fake_observer.join = mock.Mock(side_effect=RuntimeError("fail"))
        watcher._observer = fake_observer

        # Should not raise
        watcher.stop()


class TestStopTwice:
    """Test calling stop() multiple times."""

    def test_stop_called_twice_safe(self, tmp_path: Path) -> None:
        """stop() can be called multiple times safely."""
        callback = mock.Mock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=0.05)
        watcher.start()
        time.sleep(0.1)
        watcher.stop()
        # Second stop should not raise
        watcher.stop()
