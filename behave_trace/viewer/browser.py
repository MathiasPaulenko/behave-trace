"""Open the trace viewer in a browser window.

Primary: chrome --app (window without browser chrome, looks native).
Fallback: webbrowser.open() (standard tab).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser


def open_app(url: str) -> None:
    """Open the given URL in an app-like browser window.

    Tries chrome --app first, falls back to webbrowser.open().
    """
    chrome = _find_chrome()
    if chrome:
        try:
            subprocess.Popen(
                [chrome, "--app=" + url, "--new-window"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass
    webbrowser.open(url)


def _find_chrome() -> str | None:
    """Find a Chrome/Chromium executable."""
    if sys.platform == "win32":
        candidates = [
            shutil.which("chrome"),
            shutil.which("chromium"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            shutil.which("chrome"),
            shutil.which("chromium"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
        ]
    for c in candidates:
        if c:
            return c
    return None
