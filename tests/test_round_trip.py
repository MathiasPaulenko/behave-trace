"""Round-trip fidelity tests for serializer.

Verify that save → load → save produces identical JSON (idempotency).
"""

from __future__ import annotations

import json
from pathlib import Path

from behave_trace.models import (
    Artifact,
    Background,
    DataTable,
    Environment,
    ErrorInfo,
    Feature,
    Scenario,
    Step,
    Trace,
    TraceStats,
)
from behave_trace.serializer import Serializer


def _make_full_trace() -> Trace:
    """Create a trace with all fields populated."""
    trace = Trace(version="1")
    trace.environment = Environment(
        python_version="3.13",
        behave_version="1.3.0",
        behave_trace_version="1.2.1",
        platform="linux",
        hostname="test-host",
        cwd="/tmp",
        command="behave",
        user="tester",
        cpu_count=4,
        memory_mb=8192,
        git_branch="main",
        git_commit="abc123",
        git_remote="origin",
        env_vars={"PATH": "/usr/bin", "HOME": "/home/user"},
    )
    feature = Feature(
        name="Test Feature",
        status="passed",
        duration=1.5,
        description="A test feature",
        location="features/test.feature:1",
        tags=["@smoke", "@fast"],
    )
    bg = Background(
        name="Background",
        keyword="Background",
        location="features/test.feature:3",
    )
    bg_step = Step(
        keyword="Given",
        name="background step",
        status="passed",
        duration=0.1,
        location="features/test.feature:4",
    )
    bg.steps.append(bg_step)
    feature.background = bg

    scenario = Scenario(
        name="Test Scenario",
        status="passed",
        duration=1.4,
        description="A test scenario",
        location="features/test.feature:6",
        tags=["@smoke"],
        feature_name="Test Feature",
        rule_name="",
        is_outline=False,
        outline_name="",
    )
    step = Step(
        keyword="Given",
        name="a step",
        status="passed",
        duration=0.5,
        location="features/test.feature:7",
        text="some text",
        logs=["log line 1", {"level": "info", "message": "dict log"}],
    )
    step.artifacts.append(
        Artifact(
            type="screenshot",
            name="screenshot.png",
            mime_type="image/png",
            data_base64="iVBORw0KGgo=",
        )
    )
    step.artifacts.append(
        Artifact(
            type="dom",
            name="dom.html",
            mime_type="text/html",
            text="<html></html>",
        )
    )
    step.error = ErrorInfo(
        message="Something went wrong",
        traceback="Traceback...",
        exception_type="ValueError",
    )
    step.table = DataTable(
        headings=["col1", "col2"],
        rows=[["a", "b"], ["c", "d"]],
    )
    scenario.steps.append(step)
    feature.scenarios.append(scenario)

    # Add a failed scenario for stats diversity
    failed_scenario = Scenario(
        name="Failed Scenario",
        status="failed",
        duration=0.3,
        feature_name="Test Feature",
    )
    failed_step = Step(keyword="When", name="bad step", status="failed", duration=0.1)
    failed_scenario.steps.append(failed_step)
    feature.scenarios.append(failed_scenario)

    trace.features.append(feature)

    trace.stats = TraceStats(
        total_features=1,
        total_scenarios=2,
        total_steps=3,
        by_status={"passed": 1, "failed": 1},
        duration=1.5,
        total_artifacts=2,
        total_screenshots=1,
        total_logs=2,
        slowest_step_duration=0.5,
        slowest_step_name="Given a step",
        avg_step_duration=0.2,
    )
    return trace


class TestSerializerRoundTrip:
    """Verify save → load → save idempotency."""

    def test_round_trip_preserves_core_data(self, tmp_path: Path) -> None:
        """Core data survives a save-load cycle."""
        trace = _make_full_trace()
        p1 = tmp_path / "trace1.json"
        Serializer.save(trace, p1)
        loaded = Serializer.load(p1)

        assert loaded.version == trace.version
        assert len(loaded.features) == 1
        f = loaded.features[0]
        assert f.name == "Test Feature"
        assert f.status == "passed"
        assert f.duration == 1.5
        assert f.description == "A test feature"
        assert f.location == "features/test.feature:1"
        assert f.tags == ["@smoke", "@fast"]
        assert f.background is not None
        assert len(f.background.steps) == 1
        assert f.background.steps[0].name == "background step"
        assert len(f.scenarios) == 2

        s = f.scenarios[0]
        assert s.name == "Test Scenario"
        assert s.status == "passed"
        assert s.duration == 1.4
        assert s.feature_name == "Test Feature"
        assert s.is_outline is False
        assert len(s.steps) == 1

        st = s.steps[0]
        assert st.keyword == "Given"
        assert st.name == "a step"
        assert st.status == "passed"
        assert st.duration == 0.5
        assert st.text == "some text"
        assert len(st.artifacts) == 2
        assert st.artifacts[0].type == "screenshot"
        assert st.artifacts[0].data_base64 == "iVBORw0KGgo="
        assert st.artifacts[1].type == "dom"
        assert st.artifacts[1].text == "<html></html>"
        assert st.error is not None
        assert st.error.message == "Something went wrong"
        assert st.error.exception_type == "ValueError"
        assert st.table is not None
        assert st.table.headings == ["col1", "col2"]
        assert st.table.rows == [["a", "b"], ["c", "d"]]
        assert len(st.logs) == 2
        assert st.logs[0] == "log line 1"
        assert st.logs[1] == {"level": "info", "message": "dict log"}

    def test_round_trip_preserves_environment(self, tmp_path: Path) -> None:
        """Environment data survives a save-load cycle."""
        trace = _make_full_trace()
        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        env = loaded.environment
        assert env.python_version == "3.13"
        assert env.behave_version == "1.3.0"
        assert env.behave_trace_version == "1.2.1"
        assert env.platform == "linux"
        assert env.hostname == "test-host"
        assert env.cwd == "/tmp"
        assert env.command == "behave"
        assert env.user == "tester"
        assert env.cpu_count == 4
        assert env.memory_mb == 8192
        assert env.git_branch == "main"
        assert env.git_commit == "abc123"
        assert env.git_remote == "origin"
        assert env.env_vars == {"PATH": "/usr/bin", "HOME": "/home/user"}

    def test_round_trip_preserves_stats(self, tmp_path: Path) -> None:
        """Stats data survives a save-load cycle."""
        trace = _make_full_trace()
        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        stats = loaded.stats
        assert stats.total_features == 1
        assert stats.total_scenarios == 2
        assert stats.total_steps == 3
        assert stats.by_status == {"passed": 1, "failed": 1}
        assert stats.duration == 1.5
        assert stats.total_artifacts == 2
        assert stats.total_screenshots == 1
        assert stats.total_logs == 2
        assert stats.slowest_step_duration == 0.5
        assert stats.slowest_step_name == "Given a step"
        assert stats.avg_step_duration == 0.2

    def test_double_save_idempotent(self, tmp_path: Path) -> None:
        """save → load → save produces the same JSON (ignoring created_at)."""
        trace = _make_full_trace()
        p1 = tmp_path / "trace1.json"
        p2 = tmp_path / "trace2.json"
        Serializer.save(trace, p1)
        loaded = Serializer.load(p1)
        Serializer.save(loaded, p2)

        data1 = json.loads(p1.read_text())
        data2 = json.loads(p2.read_text())

        # created_at may differ slightly due to timing, but should be same
        # since we reuse the loaded value
        assert data1["created_at"] == data2["created_at"]

        # Remove created_at for comparison
        data1.pop("created_at")
        data2.pop("created_at")

        assert data1 == data2

    def test_round_trip_with_empty_collections(self, tmp_path: Path) -> None:
        """Trace with empty collections round-trips correctly."""
        trace = Trace()
        f = Feature(name="empty")
        s = Scenario(name="empty")
        s.steps.append(Step(keyword="Given", name="step", artifacts=[], logs=[]))
        f.scenarios.append(s)
        trace.features.append(f)

        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        assert len(loaded.features) == 1
        assert len(loaded.features[0].scenarios) == 1
        assert len(loaded.features[0].scenarios[0].steps) == 1
        assert loaded.features[0].scenarios[0].steps[0].artifacts == []
        assert loaded.features[0].scenarios[0].steps[0].logs == []

    def test_round_trip_with_special_characters(self, tmp_path: Path) -> None:
        """Special characters in names survive round-trip."""
        trace = Trace()
        f = Feature(name='Feature with "quotes" & <html> and \n newline')
        s = Scenario(name="Scenario with \t tab and \r carriage return")
        s.steps.append(Step(keyword="Given", name="Step with \\ backslash and $ dollar"))
        f.scenarios.append(s)
        trace.features.append(f)

        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        assert loaded.features[0].name == 'Feature with "quotes" & <html> and \n newline'
        assert loaded.features[0].scenarios[0].name == "Scenario with \t tab and \r carriage return"
        assert (
            loaded.features[0].scenarios[0].steps[0].name == "Step with \\ backslash and $ dollar"
        )
