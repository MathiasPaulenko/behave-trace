"""Tests for behave_trace.runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from behave_trace.runner import BehaveRunner, RunResult


class TestBuildCommand:
    def test_basic_command(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        cmd = runner.build_command("features/", "trace.json")
        assert "behave" in cmd[0]
        assert "--format" in cmd
        assert "behave-trace" in cmd
        assert "-o" in cmd
        assert "trace.json" in cmd
        assert "features/" in cmd

    def test_with_tags(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        cmd = runner.build_command(".", "out.json", tags="@smoke")
        assert "--tags" in cmd
        assert "@smoke" in cmd

    def test_with_extra_args(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        cmd = runner.build_command(".", "out.json", extra_args=["--no-capture", "--verbose"])
        assert "--no-capture" in cmd
        assert "--verbose" in cmd

    def test_module_fallback(self) -> None:
        runner = BehaveRunner(behave_executable=None)
        # When behave is not on PATH, it falls back to python -m behave
        # The actual behavior depends on the test environment
        cmd = runner.build_command(".", "out.json")
        # Either "behave" or "python -m behave"
        assert "-o" in cmd
        assert "out.json" in cmd


class TestRun:
    def test_run_success(self, tmp_path: Path) -> None:
        """Test that run executes behave and returns a RunResult."""
        runner = BehaveRunner(behave_executable="behave")
        output_path = tmp_path / "trace.json"

        # Mock subprocess.run to simulate behave producing a trace file
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Feature: Test\n  Scenario: Test\n"
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            # Create the trace file so trace_path.exists() returns True
            output_path.write_text('{"version": "1"}', encoding="utf-8")
            result = runner.run(".", output_path)

        assert result.returncode == 0
        assert "Feature: Test" in result.stdout
        assert result.trace_path == output_path

    def test_run_failure(self, tmp_path: Path) -> None:
        """Test that run handles behave failure."""
        runner = BehaveRunner(behave_executable="behave")
        output_path = tmp_path / "trace.json"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: step not found\n"

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            result = runner.run(".", output_path)

        assert result.returncode == 1
        assert "Error" in result.stderr
        # trace_path is None because the file doesn't exist
        assert result.trace_path is None

    def test_run_with_cwd(self, tmp_path: Path) -> None:
        """Test that run passes cwd to subprocess."""
        runner = BehaveRunner(behave_executable="behave")
        output_path = tmp_path / "trace.json"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            output_path.write_text("{}", encoding="utf-8")
            result = runner.run(".", output_path, cwd=tmp_path)

        assert result.returncode == 0
        # Verify cwd was passed
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cwd"] == str(tmp_path)

    def test_run_with_cwd_resolves_trace_path(self, tmp_path: Path) -> None:
        """Regression: trace_path should be resolved relative to cwd when
        checking for existence, since behave creates the file in cwd."""
        runner = BehaveRunner(behave_executable="behave")
        cwd = tmp_path / "project"
        cwd.mkdir()
        # Simulate behave writing trace.json inside cwd, not the caller's dir
        (cwd / "trace.json").write_text('{"version": "1"}', encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            result = runner.run(".", "trace.json", cwd=cwd)

        assert result.trace_path is not None
        assert result.trace_path == cwd / "trace.json"

    def test_run_with_cwd_trace_not_found(self, tmp_path: Path) -> None:
        """Regression: when cwd is set and trace doesn't exist, trace_path
        should be None."""
        runner = BehaveRunner(behave_executable="behave")
        cwd = tmp_path / "project"
        cwd.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            result = runner.run(".", "trace.json", cwd=cwd)

        assert result.trace_path is None


class TestRunAndLoad:
    def test_run_and_load_success(self, tmp_path: Path) -> None:
        """Test that run_and_load returns a Trace object."""
        from behave_trace.models import Trace
        from behave_trace.serializer import Serializer

        # Create a real trace file
        trace = Trace()
        trace_path = tmp_path / "trace.json"
        Serializer.save(trace, trace_path)

        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            result, loaded_trace = runner.run_and_load(".", trace_path)

        assert result.returncode == 0
        assert loaded_trace is not None
        assert isinstance(loaded_trace, Trace)

    def test_run_and_load_no_trace_file(self, tmp_path: Path) -> None:
        """Test that run_and_load returns None when no trace is produced."""
        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result):
            result, loaded_trace = runner.run_and_load(".", tmp_path / "nonexistent.json")

        assert result.returncode == 1
        assert loaded_trace is None


class TestRunResult:
    def test_defaults(self) -> None:
        result = RunResult(returncode=0, stdout="", stderr="")
        assert result.returncode == 0
        assert result.trace_path is None

    def test_with_trace_path(self, tmp_path: Path) -> None:
        path = tmp_path / "trace.json"
        result = RunResult(returncode=0, stdout="", stderr="", trace_path=path)
        assert result.trace_path == path


class TestRunFiltered:
    def test_with_scenario_names_adds_name_flags(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            runner.run_filtered(
                features_dir="features/",
                output_path="trace.json",
                scenario_names=["Scenario A", "Scenario B"],
            )

        cmd = mock_run.call_args[0][0]
        assert "--name" in cmd
        assert "Scenario A" in cmd
        assert "Scenario B" in cmd
        # Two --name flags
        assert cmd.count("--name") == 2

    def test_without_scenario_names_no_name_flags(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            runner.run_filtered(
                features_dir="features/",
                output_path="trace.json",
                scenario_names=None,
            )

        cmd = mock_run.call_args[0][0]
        assert "--name" not in cmd

    def test_with_empty_scenario_names_no_name_flags(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            runner.run_filtered(
                features_dir="features/",
                output_path="trace.json",
                scenario_names=[],
            )

        cmd = mock_run.call_args[0][0]
        assert "--name" not in cmd

    def test_with_tags_and_scenario_names(self) -> None:
        runner = BehaveRunner(behave_executable="behave")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            runner.run_filtered(
                features_dir="features/",
                output_path="trace.json",
                tags="@smoke",
                scenario_names=["My Scenario"],
            )

        cmd = mock_run.call_args[0][0]
        assert "--tags" in cmd
        assert "@smoke" in cmd
        assert "--name" in cmd
        assert "My Scenario" in cmd


class TestRunWithServerUrl:
    """Regression tests for server_url environment injection."""

    def test_server_url_does_not_raise_nameerror(self, tmp_path: Path) -> None:
        """Regression: ``os`` was only imported inside a conditional block.

        When ``server_url`` is set but the candidate-root check fails (e.g.
        installed package), ``os.environ.copy()`` raised ``NameError``.
        """
        runner = BehaveRunner(behave_executable="behave")
        output_path = tmp_path / "trace.json"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        output_path.write_text("{}", encoding="utf-8")

        with patch("behave_trace.runner.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run(".", output_path, server_url="http://localhost:8000")

        assert result.returncode == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["env"] is not None
        assert call_kwargs["env"]["BEHAVE_TRACE_SERVER_URL"] == "http://localhost:8000"
