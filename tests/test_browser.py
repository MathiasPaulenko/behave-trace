"""Tests for the browser opening module."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from behave_trace.viewer import browser


class TestOpenApp:
    """Tests for open_app()."""

    def test_open_app_with_chrome_found(self) -> None:
        """When Chrome is found, launch it with --app flag."""
        with (
            mock.patch.object(browser, "_find_chrome", return_value="/usr/bin/chrome"),
            mock.patch.object(browser.subprocess, "Popen") as mock_popen,
        ):
            browser.open_app("http://127.0.0.1:8080")
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert "--app=http://127.0.0.1:8080" in args

    def test_open_app_chrome_launch_fails_falls_back_to_webbrowser(self) -> None:
        """When Chrome Popen raises, fall back to webbrowser.open."""
        with (
            mock.patch.object(browser, "_find_chrome", return_value="/usr/bin/chrome"),
            mock.patch.object(browser.subprocess, "Popen", side_effect=OSError("boom")),
            mock.patch.object(browser.webbrowser, "open") as mock_open,
        ):
            browser.open_app("http://127.0.0.1:8080")
            mock_open.assert_called_once_with("http://127.0.0.1:8080")

    def test_open_app_no_chrome_uses_webbrowser(self) -> None:
        """When no Chrome is found, use webbrowser.open directly."""
        with (
            mock.patch.object(browser, "_find_chrome", return_value=None),
            mock.patch.object(browser.webbrowser, "open") as mock_open,
        ):
            browser.open_app("http://127.0.0.1:8080")
            mock_open.assert_called_once_with("http://127.0.0.1:8080")


class TestFindChrome:
    """Tests for _find_chrome()."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific Chrome path candidates")
    def test_find_chrome_windows_returns_first_match(self) -> None:
        """On Windows, return the first available candidate."""
        with mock.patch.object(browser.shutil, "which", return_value=r"C:\chrome.exe"):
            result = browser._find_chrome()
            assert result is not None

    def test_find_chrome_returns_none_when_nothing_found(self) -> None:
        """Return None when no Chrome executable is available on non-Windows."""
        # On Windows, hardcoded paths are always truthy strings.
        # Simulate a platform without hardcoded paths by mocking sys.platform.
        with (
            mock.patch.object(browser.sys, "platform", "linux"),
            mock.patch.object(browser.shutil, "which", return_value=None),
        ):
            result = browser._find_chrome()
            assert result is None

    def test_find_chrome_returns_which_result(self) -> None:
        """Return the result of shutil.which when it finds something."""
        with mock.patch.object(browser.shutil, "which", return_value="/usr/bin/google-chrome"):
            result = browser._find_chrome()
            assert result == "/usr/bin/google-chrome"
