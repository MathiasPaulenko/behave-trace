"""Integration tests: run Behave with behave-trace formatter and verify output."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from behave_trace.serializer import Serializer

FEATURES_DIR = Path(__file__).parent / "features"

behave_available = shutil.which("behave") is not None or (
    subprocess.run(
        [sys.executable, "-m", "behave", "--version"],
        capture_output=True,
    ).returncode
    == 0
)


def _run_behave(trace_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run behave with the behave-trace formatter.

    Uses ``python -m behave`` to ensure the same Python environment that
    has ``behave_trace`` installed. Behave 1.3.x doesn't auto-discover
    entry points, so we use the scoped name
    ``behave_trace.formatter:TraceFormatter`` which Behave resolves
    natively via ``module:Class`` syntax.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "behave",
            "--format",
            "behave_trace.formatter:TraceFormatter",
            "-o",
            str(trace_path),
            str(FEATURES_DIR),
        ],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


@pytest.mark.integration
@pytest.mark.skipif(not behave_available, reason="behave not in PATH")
class TestFormatterCapture:
    def test_generates_trace_json(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "trace.json"

        result = _run_behave(trace_path, tmp_path)

        # Behave exits non-zero when a scenario fails — that's expected
        assert trace_path.exists(), (
            f"trace.json not generated.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        trace = Serializer.load(trace_path)

        # Feature
        assert len(trace.features) == 1
        feature = trace.features[0]
        assert "Simple test feature" in feature.name

        # Scenarios
        assert len(feature.scenarios) == 2

        statuses = {s.status for s in feature.scenarios}
        assert "passed" in statuses
        assert "failed" in statuses

        # Steps have durations
        for scenario in feature.scenarios:
            for step in scenario.steps:
                assert step.duration >= 0.0

        # Stats
        assert trace.stats.total_steps > 0
        assert "failed" in trace.stats.by_status
        # by_status counts features; verify scenario statuses separately
        scenario_statuses = {s.status for f in trace.features for s in f.scenarios}
        assert "passed" in scenario_statuses
        assert "failed" in scenario_statuses

        # Environment
        assert trace.environment.python_version != ""

    def test_stats_match_actual_content(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "trace.json"

        _run_behave(trace_path, tmp_path)

        assert trace_path.exists()
        trace = Serializer.load(trace_path)

        # Count steps manually
        manual_step_count = sum(len(s.steps) for f in trace.features for s in f.scenarios)
        assert trace.stats.total_steps == manual_step_count

        # Count scenarios manually
        manual_scenario_count = sum(len(f.scenarios) for f in trace.features)
        assert trace.stats.total_scenarios == manual_scenario_count

    def test_failed_step_has_error(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "trace.json"

        _run_behave(trace_path, tmp_path)

        assert trace_path.exists()
        trace = Serializer.load(trace_path)

        failed_scenario = None
        for scenario in trace.features[0].scenarios:
            if scenario.status == "failed":
                failed_scenario = scenario
                break

        assert failed_scenario is not None, "No failed scenario found"

        failed_step = None
        for step in failed_scenario.steps:
            if step.status == "failed":
                failed_step = step
                break

        assert failed_step is not None, "No failed step found"
        assert failed_step.error is not None
        assert "Intentional failure" in failed_step.error.message

    def test_environment_captured(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "trace.json"

        _run_behave(trace_path, tmp_path)

        assert trace_path.exists()
        trace = Serializer.load(trace_path)

        env = trace.environment
        assert env.platform != ""
        assert env.hostname != ""
        assert env.behave_version != ""
