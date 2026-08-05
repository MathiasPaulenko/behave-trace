"""Tests for the __main__ entry point."""

from __future__ import annotations

import subprocess
import sys


class TestMainEntry:
    """Tests for python -m behave_trace."""

    def test_main_version(self) -> None:
        """Running python -m behave_trace --version prints version."""
        result = subprocess.run(
            [sys.executable, "-m", "behave_trace", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "behave-trace" in result.stdout

    def test_main_no_command_prints_help(self) -> None:
        """Running python -m behave_trace without a subcommand prints help."""
        result = subprocess.run(
            [sys.executable, "-m", "behave_trace"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()
