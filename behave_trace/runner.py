"""Run behave as a subprocess and load the resulting trace.

This module bridges the gap between behave execution and the trace viewer,
enabling the ``behave-trace run`` command (equivalent to ``playwright test --ui``).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from behave_trace.serializer import Serializer

if TYPE_CHECKING:
    from behave_trace.models import Trace


@dataclass(slots=True)
class RunResult:
    """Outcome of a behave run."""

    returncode: int
    stdout: str
    stderr: str
    trace_path: Path | None = None


class BehaveRunner:
    """Execute behave as a subprocess and load the resulting trace.

    Args:
        behave_executable: Path to the behave executable.
            Defaults to ``behave`` found on PATH (or ``python -m behave``).
    """

    def __init__(self, behave_executable: str | Path | None = None) -> None:
        if behave_executable:
            self._behave = str(behave_executable)
            self._use_module = False
        else:
            # Always use `python -m behave` to guarantee the same interpreter
            # and make behave_trace importable for the formatter.
            self._behave = sys.executable
            self._use_module = True

    def build_command(
        self,
        features_dir: str | Path = ".",
        output_path: str | Path = "trace.json",
        tags: str | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build the behave command line without executing it.

        Args:
            features_dir: Directory containing .feature files.
            output_path: Where the trace JSON will be written.
            tags: Optional tag expression (e.g. ``@smoke``).
            extra_args: Additional arguments to pass to behave.

        Returns:
            The command list suitable for :func:`subprocess.run`.
        """
        cmd = [sys.executable, "-m", "behave"] if self._use_module else [self._behave]

        cmd.extend(["--format", "behave-trace", "-o", str(output_path)])
        if tags:
            cmd.extend(["--tags", tags])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(str(features_dir))
        return cmd

    def run(
        self,
        features_dir: str | Path = ".",
        output_path: str | Path = "trace.json",
        tags: str | None = None,
        extra_args: list[str] | None = None,
        cwd: str | Path | None = None,
        server_url: str | None = None,
    ) -> RunResult:
        """Execute behave and return the result.

        Args:
            features_dir: Directory containing .feature files.
            output_path: Where the trace JSON will be written.
            tags: Optional tag expression.
            extra_args: Additional arguments for behave.
            cwd: Working directory for the subprocess.

        Returns:
            :class:`RunResult` with exit code, output, and trace path.
        """
        cmd = self.build_command(features_dir, output_path, tags, extra_args)

        # Ensure behave_trace is importable in the subprocess. When the package
        # is not installed (e.g. running from source), we inject the project
        # root into PYTHONPATH so the formatter registration in behave.ini works.
        env = None
        candidate_root = Path(__file__).resolve().parent.parent
        if (candidate_root / "behave_trace" / "__init__.py").exists():
            import os

            env = os.environ.copy()
            existing = env.get("PYTHONPATH", "")
            if existing:
                env["PYTHONPATH"] = f"{candidate_root}{os.pathsep}{existing}"
            else:
                env["PYTHONPATH"] = str(candidate_root)

        if server_url:
            env = env or os.environ.copy()
            env["BEHAVE_TRACE_SERVER_URL"] = str(server_url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        trace_path = Path(output_path)
        if cwd:
            trace_path = Path(cwd) / trace_path
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            trace_path=trace_path if trace_path.exists() else None,
        )

    def run_and_load(
        self,
        features_dir: str | Path = ".",
        output_path: str | Path = "trace.json",
        tags: str | None = None,
        extra_args: list[str] | None = None,
        cwd: str | Path | None = None,
    ) -> tuple[RunResult, Trace | None]:
        """Execute behave and load the resulting trace.

        Returns a tuple of (RunResult, Trace | None).
        If behave fails to produce a trace file, the second element is None.
        """

        result = self.run(
            features_dir=features_dir,
            output_path=output_path,
            tags=tags,
            extra_args=extra_args,
            cwd=cwd,
        )
        if result.trace_path and result.trace_path.exists():
            try:
                trace = Serializer.load(result.trace_path)
                return result, trace
            except Exception:
                return result, None
        return result, None

    def run_filtered(
        self,
        features_dir: str | Path = ".",
        output_path: str | Path = "trace.json",
        tags: str | None = None,
        scenario_names: list[str] | None = None,
        cwd: str | Path | None = None,
        server_url: str | None = None,
    ) -> RunResult:
        """Execute behave filtered by scenario names.

        Uses ``--name`` flags to select specific scenarios. If
        ``scenario_names`` is None or empty, behaves like :meth:`run`.

        Args:
            features_dir: Directory containing .feature files.
            output_path: Where the trace JSON will be written.
            tags: Optional tag expression.
            scenario_names: List of scenario names to run.
            cwd: Working directory for the subprocess.

        Returns:
            :class:`RunResult` with exit code, output, and trace path.
        """
        extra_args: list[str] = []
        if scenario_names:
            for name in scenario_names:
                extra_args.extend(["--name", name])
        return self.run(
            features_dir=features_dir,
            output_path=output_path,
            tags=tags,
            extra_args=extra_args,
            cwd=cwd,
            server_url=server_url,
        )
