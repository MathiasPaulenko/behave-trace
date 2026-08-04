"""File watcher for watch mode.

Observes changes in ``*.feature`` and ``*.py`` files within a directory
and triggers a callback after a debounce period.

Uses ``watchdog`` when available for efficient event-driven notifications.
Falls back to a simple polling mechanism when ``watchdog`` is not installed.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from pathlib import Path

# File extensions to watch
_WATCHED_EXTENSIONS = frozenset({".feature", ".py"})

# Default debounce in milliseconds
_DEFAULT_DEBOUNCE_MS = 500


class FileWatcher:
    """Watch a directory for file changes and call a callback.

    Args:
        directory: The root directory to watch (recursively).
        callback: Called with a list of changed file paths (as strings).
        debounce_ms: Minimum time between callbacks to avoid bursts.
    """

    def __init__(
        self,
        directory: str | Path,
        callback: Callable[[list[str]], None],
        debounce_ms: int = _DEFAULT_DEBOUNCE_MS,
    ) -> None:
        self._directory = Path(directory)
        self._callback = callback
        self._debounce_s = debounce_ms / 1000.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._observer: object | None = None
        self._pending_files: set[str] = set()
        self._pending_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None

    def start(self) -> None:
        """Start watching. Returns immediately; runs in a background thread."""
        self._stop_event.clear()
        try:
            self._start_watchdog()
        except ImportError:
            self._start_polling()
        except OSError:
            # watchdog fails on non-existent directories
            self._start_polling()

    def stop(self) -> None:
        """Stop watching and wait for the background thread to finish."""
        self._stop_event.set()
        with self._pending_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
        if self._observer is not None:
            try:
                self._observer.stop()  # type: ignore[attr-defined]
                self._observer.join()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._observer = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    @property
    def is_watchdog(self) -> bool:
        """Whether watchdog is available and being used."""
        return self._observer is not None

    # ------------------------------------------------------------------
    # Watchdog backend
    # ------------------------------------------------------------------

    def _start_watchdog(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event: object) -> None:
                if getattr(event, "is_directory", False):
                    return
                path = getattr(event, "src_path", "")
                if not _is_watched(path):
                    return
                watcher._on_file_changed(path)

            def on_created(self, event: object) -> None:
                self.on_modified(event)

        observer = Observer()
        observer.schedule(Handler(), str(self._directory), recursive=True)
        observer.start()
        self._observer = observer

    # ------------------------------------------------------------------
    # Shared debounce logic
    # ------------------------------------------------------------------

    def _on_file_changed(self, path: str) -> None:
        """Called by either backend when a watched file changes."""
        with self._pending_lock:
            self._pending_files.add(path)
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(self._debounce_s, self._fire_callback)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _fire_callback(self) -> None:
        """Fire the callback with all pending files."""
        if self._stop_event.is_set():
            return
        with self._pending_lock:
            if not self._pending_files:
                return
            files = sorted(self._pending_files)
            self._pending_files.clear()
            self._debounce_timer = None
        self._callback(files)

    # ------------------------------------------------------------------
    # Polling fallback
    # ------------------------------------------------------------------

    def _start_polling(self) -> None:
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:
        snapshots: dict[Path, float] = {}
        for f in self._scan_files():
            with contextlib.suppress(OSError):
                snapshots[f] = f.stat().st_mtime

        while not self._stop_event.wait(timeout=self._debounce_s):
            changed: list[str] = []
            current_files: set[Path] = set()

            for f in self._scan_files():
                current_files.add(f)
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                if f not in snapshots or snapshots[f] != mtime:
                    changed.append(str(f))
                    snapshots[f] = mtime

            for f in list(snapshots):
                if f not in current_files:
                    del snapshots[f]

            if changed:
                self._callback(changed)

    def _scan_files(self) -> list[Path]:
        if not self._directory.exists():
            return []
        try:
            return [f for f in self._directory.rglob("*") if f.is_file() and _is_watched(str(f))]
        except OSError:
            return []


def _is_watched(path: str) -> bool:
    """Check if a file path has a watched extension."""
    return Path(path).suffix in _WATCHED_EXTENSIONS
