"""Tests for behave_trace.serializer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from behave_trace.models import (
    ARTIFACT_DOM,
    ARTIFACT_SCREENSHOT,
    STATUS_FAILED,
    STATUS_PASSED,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trace() -> Trace:
    """Build a trace with features, scenarios, steps, artifacts, error, table."""
    step1 = Step(
        keyword="Given",
        name="I do something",
        status=STATUS_PASSED,
        duration=0.15,
        location="steps.py:10",
        logs=["log line 1", "log line 2"],
    )
    step2 = Step(
        keyword="Then",
        name="I verify result",
        status=STATUS_FAILED,
        duration=0.42,
        location="steps.py:20",
        error=ErrorInfo(
            message="Assertion failed",
            traceback="Traceback (most recent call last):\n  ...",
            exception_type="AssertionError",
        ),
        artifacts=[
            Artifact(
                type=ARTIFACT_SCREENSHOT,
                name="screenshot.png",
                mime_type="image/png",
                data_base64="iVBORw0KGgo=",
            ),
            Artifact(
                type=ARTIFACT_DOM,
                name="dom.html",
                mime_type="text/html",
                text="<html><body>hello</body></html>",
            ),
        ],
        table=DataTable(headings=["col1", "col2"], rows=[["a", "b"], ["c", "d"]]),
    )
    scenario = Scenario(
        name="My scenario",
        status=STATUS_FAILED,
        duration=0.57,
        description="A test scenario",
        location="feature.feature:5",
        tags=["@smoke"],
        steps=[step1, step2],
        feature_name="My feature",
        is_outline=False,
    )
    bg = Background(
        name="",
        keyword="Background",
        location="feature.feature:3",
        steps=[Step(keyword="Given", name="background step", status=STATUS_PASSED, duration=0.01)],
    )
    feature = Feature(
        name="My feature",
        status=STATUS_FAILED,
        duration=0.57,
        description="Feature description",
        location="feature.feature:1",
        tags=["@feature-tag"],
        scenarios=[scenario],
        background=bg,
    )
    env = Environment(
        python_version="3.12.0",
        behave_version="1.3.3",
        behave_trace_version="0.1.0",
        platform="Linux 6.5.0 (x86_64)",
        hostname="test-host",
        cwd="/tmp/test",
        command="behave --format behave-trace",
        user="tester",
        cpu_count=8,
        git_branch="main",
        git_commit="abc1234",
        git_remote="git@github.com:test/repo.git",
    )
    stats = TraceStats(
        total_features=1,
        total_scenarios=1,
        total_steps=2,
        by_status={"failed": 1},
        duration=0.57,
        start_time=datetime(2025, 1, 1, 12, 0, 0),
        end_time=datetime(2025, 1, 1, 12, 0, 1),
        total_artifacts=2,
        total_screenshots=1,
        total_logs=2,
        slowest_step_duration=0.42,
        slowest_step_name="Then I verify result",
        avg_step_duration=0.285,
    )
    return Trace(
        version="1",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
        features=[feature],
        environment=env,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


class TestSave:
    def test_creates_file(self, tmp_path: Path) -> None:
        trace = make_trace()
        path = tmp_path / "trace.json"
        result = Serializer.save(trace, path)
        assert path.exists()
        assert result == path

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        trace = make_trace()
        path = tmp_path / "nested" / "deep" / "trace.json"
        Serializer.save(trace, path)
        assert path.exists()

    def test_valid_json(self, tmp_path: Path) -> None:
        trace = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == "1"
        assert len(data["features"]) == 1

    def test_empty_trace(self, tmp_path: Path) -> None:
        trace = Trace()
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["features"] == []


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            Serializer.load(tmp_path / "nonexistent.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            Serializer.load(path)


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_full_roundtrip(self, tmp_path: Path) -> None:
        original = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)

        # Trace-level
        assert loaded.version == original.version

        # Feature
        assert len(loaded.features) == 1
        f = loaded.features[0]
        assert f.name == "My feature"
        assert f.status == STATUS_FAILED
        assert f.duration == 0.57
        assert f.description == "Feature description"
        assert f.location == "feature.feature:1"
        assert f.tags == ["@feature-tag"]
        assert f.scenario_count == 1

        # Background
        assert f.background is not None
        assert len(f.background.steps) == 1
        assert f.background.steps[0].name == "background step"

        # Scenario
        s = f.scenarios[0]
        assert s.name == "My scenario"
        assert s.status == STATUS_FAILED
        assert s.duration == 0.57
        assert s.description == "A test scenario"
        assert s.location == "feature.feature:5"
        assert s.tags == ["@smoke"]
        assert s.feature_name == "My feature"
        assert s.is_outline is False
        assert s.step_count == 2

        # Step 1
        st1 = s.steps[0]
        assert st1.keyword == "Given"
        assert st1.name == "I do something"
        assert st1.status == STATUS_PASSED
        assert st1.duration == 0.15
        assert st1.location == "steps.py:10"
        assert st1.logs == ["log line 1", "log line 2"]

        # Step 2
        st2 = s.steps[1]
        assert st2.keyword == "Then"
        assert st2.name == "I verify result"
        assert st2.status == STATUS_FAILED
        assert st2.duration == 0.42

        # Error
        assert st2.error is not None
        assert st2.error.message == "Assertion failed"
        assert st2.error.exception_type == "AssertionError"
        assert "Traceback" in st2.error.traceback

        # Artifacts
        assert len(st2.artifacts) == 2
        assert st2.artifacts[0].type == ARTIFACT_SCREENSHOT
        assert st2.artifacts[0].name == "screenshot.png"
        assert st2.artifacts[0].mime_type == "image/png"
        assert st2.artifacts[0].data_base64 == "iVBORw0KGgo="
        assert st2.artifacts[1].type == ARTIFACT_DOM
        assert st2.artifacts[1].text == "<html><body>hello</body></html>"

        # Table
        assert st2.table is not None
        assert st2.table.headings == ["col1", "col2"]
        assert st2.table.rows == [["a", "b"], ["c", "d"]]

        # Computed properties still work after load
        assert st2.has_screenshot is True
        assert st2.has_dom is True

    def test_empty_trace_roundtrip(self, tmp_path: Path) -> None:
        original = Trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)
        assert loaded.features == []
        assert loaded.overall_status == "untested"

    def test_environment_roundtrip(self, tmp_path: Path) -> None:
        original = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)
        env = loaded.environment
        assert env.python_version == "3.12.0"
        assert env.behave_version == "1.3.3"
        assert env.platform == "Linux 6.5.0 (x86_64)"
        assert env.hostname == "test-host"
        assert env.user == "tester"
        assert env.cpu_count == 8
        assert env.git_branch == "main"
        assert env.git_commit == "abc1234"

    def test_stats_roundtrip(self, tmp_path: Path) -> None:
        original = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)
        stats = loaded.stats
        assert stats.total_features == 1
        assert stats.total_scenarios == 1
        assert stats.total_steps == 2
        assert stats.by_status == {"failed": 1}
        assert stats.duration == 0.57
        assert stats.total_artifacts == 2
        assert stats.total_screenshots == 1
        assert stats.total_logs == 2
        assert stats.slowest_step_duration == 0.42
        assert stats.slowest_step_name == "Then I verify result"
        assert abs(stats.avg_step_duration - 0.285) < 1e-9

    def test_stats_datetime_roundtrip(self, tmp_path: Path) -> None:
        original = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)
        assert loaded.stats.start_time == datetime(2025, 1, 1, 12, 0, 0)
        assert loaded.stats.end_time == datetime(2025, 1, 1, 12, 0, 1)

    def test_created_at_roundtrip(self, tmp_path: Path) -> None:
        original = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(original, path)
        loaded = Serializer.load(path)
        assert loaded.created_at == datetime(2025, 1, 1, 12, 0, 0)

    def test_outline_scenario_roundtrip(self, tmp_path: Path) -> None:
        trace = Trace(
            features=[
                Feature(
                    name="F",
                    scenarios=[
                        Scenario(
                            name="Outline",
                            is_outline=True,
                            outline_name="Examples 1",
                        ),
                    ],
                ),
            ],
        )
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        loaded = Serializer.load(path)
        s = loaded.features[0].scenarios[0]
        assert s.is_outline is True
        assert s.outline_name == "Examples 1"

    def test_background_in_scenario_roundtrip(self, tmp_path: Path) -> None:
        bg = Background(name="bg", steps=[Step(keyword="Given", name="bg step")])
        trace = Trace(
            features=[
                Feature(
                    name="F",
                    background=bg,
                    scenarios=[Scenario(name="S", background=bg)],
                ),
            ],
        )
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        loaded = Serializer.load(path)
        f = loaded.features[0]
        assert f.background is not None
        assert f.background.name == "bg"
        assert f.scenarios[0].background is not None
        assert f.scenarios[0].background.name == "bg"

    def test_env_vars_roundtrip(self, tmp_path: Path) -> None:
        trace = Trace(
            environment=Environment(env_vars={"CI": "true", "DEBUG": "1"}),
        )
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        loaded = Serializer.load(path)
        assert loaded.environment.env_vars == {"CI": "true", "DEBUG": "1"}

    def test_overall_status_recomputed(self, tmp_path: Path) -> None:
        trace = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        loaded = Serializer.load(path)
        # overall_status is a computed property — should recompute from features
        assert loaded.overall_status == STATUS_FAILED
