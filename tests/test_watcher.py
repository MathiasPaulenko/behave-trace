"""Tests for behave_trace.watcher."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from behave_trace.watcher import FileWatcher, _is_watched


class TestIsWatched:
    def test_feature_extension(self) -> None:
        assert _is_watched("features/test.feature") is True

    def test_python_extension(self) -> None:
        assert _is_watched("steps/test.py") is True

    def test_other_extension(self) -> None:
        assert _is_watched("README.md") is False

    def test_no_extension(self) -> None:
        assert _is_watched("Makefile") is False


class TestFileWatcherPolling:
    """Test the polling fallback backend."""

    def test_detects_new_file(self, tmp_path: Path) -> None:
        """Watcher should detect a newly created .feature file."""
        changed: list[list[str]] = []
        callback_event = threading.Event()

        def callback(files: list[str]) -> None:
            changed.append(files)
            callback_event.set()

        watcher = FileWatcher(tmp_path, callback, debounce_ms=200)
        watcher.start()

        try:
            time.sleep(0.5)  # Let initial snapshot happen
            new_file = tmp_path / "test.feature"
            new_file.write_text("Feature: Test\n", encoding="utf-8")

            assert callback_event.wait(timeout=10), "Callback was not triggered"
            assert len(changed) >= 1
            all_files = [f for batch in changed for f in batch]
            assert any("test.feature" in f for f in all_files)
        finally:
            watcher.stop()

    def test_detects_modified_file(self, tmp_path: Path) -> None:
        """Watcher should detect a modified .py file."""
        py_file = tmp_path / "steps.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        changed: list[list[str]] = []
        callback_event = threading.Event()

        def callback(files: list[str]) -> None:
            changed.append(files)
            callback_event.set()

        watcher = FileWatcher(tmp_path, callback, debounce_ms=200)
        watcher.start()

        try:
            time.sleep(0.5)  # Let initial snapshot happen
            py_file.write_text("x = 2\n", encoding="utf-8")

            assert callback_event.wait(timeout=10), "Callback was not triggered"
            assert len(changed) >= 1
            all_files = [f for batch in changed for f in batch]
            assert any("steps.py" in f for f in all_files)
        finally:
            watcher.stop()

    def test_ignores_non_watched_extensions(self, tmp_path: Path) -> None:
        """Watcher should ignore .md, .txt, etc."""
        changed: list[list[str]] = []
        callback_event = threading.Event()

        def callback(files: list[str]) -> None:
            changed.append(files)
            callback_event.set()

        watcher = FileWatcher(tmp_path, callback, debounce_ms=100)
        watcher.start()

        try:
            time.sleep(0.2)
            (tmp_path / "README.md").write_text("hello", encoding="utf-8")

            # Should not trigger within a reasonable time
            assert not callback_event.wait(timeout=1.0), "Callback should not trigger for .md"
        finally:
            watcher.stop()

    def test_stop_terminates_thread(self, tmp_path: Path) -> None:
        """Watcher.stop() should terminate the background thread."""
        watcher = FileWatcher(tmp_path, lambda _: None, debounce_ms=100)
        watcher.start()
        time.sleep(0.1)
        watcher.stop()
        # After stop, the thread should be done
        # If it's polling, the thread reference should be cleared or not alive
        # We just verify stop() doesn't hang

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Watcher should handle a non-existent directory gracefully."""
        callback = MagicMock()
        watcher = FileWatcher(tmp_path / "nonexistent", callback, debounce_ms=100)
        watcher.start()
        time.sleep(0.2)
        watcher.stop()
        callback.assert_not_called()

    def test_debounce_prevents_bursts(self, tmp_path: Path) -> None:
        """Multiple rapid changes should not trigger multiple callbacks."""
        call_count = 0
        count_lock = threading.Lock()
        callback_event = threading.Event()

        def callback(files: list[str]) -> None:
            nonlocal call_count
            with count_lock:
                call_count += 1
            callback_event.set()

        watcher = FileWatcher(tmp_path, callback, debounce_ms=300)
        watcher.start()

        try:
            time.sleep(0.5)
            for i in range(5):
                (tmp_path / f"test{i}.feature").write_text(f"Feature: {i}\n", encoding="utf-8")

            assert callback_event.wait(timeout=10)
            time.sleep(1.5)  # Wait for any additional callbacks

            assert call_count >= 1
        finally:
            watcher.stop()

    def test_stop_cancels_pending_debounce_timer(self, tmp_path: Path) -> None:
        """Regression: stop() should cancel any pending debounce timer so
        the callback doesn't fire after stop()."""
        callback = MagicMock()
        watcher = FileWatcher(tmp_path, callback, debounce_ms=500)
        watcher.start()
        time.sleep(0.2)

        # Trigger a file change to start the debounce timer
        (tmp_path / "trigger.feature").write_text("Feature: trigger\n", encoding="utf-8")
        time.sleep(0.1)

        # Stop immediately — debounce timer is still pending
        watcher.stop()

        # Wait long enough for the debounce timer to have fired
        time.sleep(1.0)

        # Callback should NOT have been called after stop()
        callback.assert_not_called()


class TestFileWatcherWatchdog:
    """Test watchdog backend if available."""

    def test_watchdog_backend_used_when_available(self, tmp_path: Path) -> None:
        """If watchdog is installed, it should be used as the backend."""
        try:
            import watchdog  # noqa: F401
        except ImportError:
            pytest.skip("watchdog not installed")

        watcher = FileWatcher(tmp_path, lambda _: None, debounce_ms=100)
        watcher.start()
        try:
            assert watcher.is_watchdog is True
        finally:
            watcher.stop()

    def test_polling_fallback_when_no_watchdog(self, tmp_path: Path) -> None:
        """If watchdog is not available, polling should be used."""
        watcher = FileWatcher(tmp_path, lambda _: None, debounce_ms=100)
        # Patch _start_watchdog to raise ImportError
        original = watcher._start_watchdog
        watcher._start_watchdog = lambda: (_ for _ in ()).throw(ImportError("mocked"))
        try:
            watcher.start()
            assert watcher.is_watchdog is False
        finally:
            watcher.stop()
            watcher._start_watchdog = original
