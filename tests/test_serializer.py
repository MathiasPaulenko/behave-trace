"""Tests for behave_trace.serializer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

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

    def test_utf8_bom_handled(self, tmp_path: Path) -> None:
        """Regression: UTF-8 BOM in trace file caused JSONDecodeError.

        Windows editors (Notepad, PowerShell) often prepend a UTF-8 BOM.
        Using utf-8-sig encoding for reading strips it transparently.
        """
        import codecs

        trace = make_trace()
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        # Re-write with BOM
        raw = path.read_text(encoding="utf-8")
        path.write_bytes(codecs.BOM_UTF8 + raw.encode("utf-8"))
        loaded = Serializer.load(path)
        assert loaded.version == trace.version
        assert len(loaded.features) == 1

    def test_list_root_raises_value_error(self, tmp_path: Path) -> None:
        """Regression: non-dict JSON root should raise ValueError, not crash."""
        path = tmp_path / "bad.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(path)

    def test_string_root_raises_value_error(self, tmp_path: Path) -> None:
        """Regression: non-dict JSON root should raise ValueError, not crash."""
        path = tmp_path / "bad.json"
        path.write_text('"hello"', encoding="utf-8")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(path)

    def test_number_root_raises_value_error(self, tmp_path: Path) -> None:
        """Regression: non-dict JSON root should raise ValueError, not crash."""
        path = tmp_path / "bad.json"
        path.write_text("42", encoding="utf-8")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(path)

    def test_null_root_raises_value_error(self, tmp_path: Path) -> None:
        """Regression: non-dict JSON root should raise ValueError, not crash."""
        path = tmp_path / "bad.json"
        path.write_text("null", encoding="utf-8")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(path)

    def test_non_dict_feature_entry_skipped(self, tmp_path: Path) -> None:
        """Regression: non-dict entries in features array should be skipped."""
        raw = {
            "version": "1",
            "features": ["not a dict", 42, None, {"name": "Valid"}],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert len(loaded.features) == 1
        assert loaded.features[0].name == "Valid"

    def test_non_dict_scenario_entry_skipped(self, tmp_path: Path) -> None:
        """Regression: non-dict entries in scenarios array should be skipped."""
        raw = {
            "version": "1",
            "features": [
                {"name": "F", "scenarios": ["bad", 42, {"name": "S"}]},
            ],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert len(loaded.features[0].scenarios) == 1
        assert loaded.features[0].scenarios[0].name == "S"

    def test_non_dict_step_entry_skipped(self, tmp_path: Path) -> None:
        """Regression: non-dict entries in steps array should be skipped."""
        raw = {
            "version": "1",
            "features": [
                {
                    "name": "F",
                    "scenarios": [
                        {"name": "S", "steps": ["bad", 42, {"keyword": "Given", "name": "step"}]},
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        steps = loaded.features[0].scenarios[0].steps
        assert len(steps) == 1
        assert steps[0].name == "step"

    def test_non_dict_artifact_entry_skipped(self, tmp_path: Path) -> None:
        """Regression: non-dict entries in artifacts array should be skipped."""
        raw = {
            "version": "1",
            "features": [
                {
                    "name": "F",
                    "scenarios": [
                        {
                            "name": "S",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "artifacts": ["bad", 42, {"type": "text", "name": "ok"}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        artifacts = loaded.features[0].scenarios[0].steps[0].artifacts
        assert len(artifacts) == 1
        assert artifacts[0].name == "ok"

    def test_non_dict_environment_falls_back_to_default(self, tmp_path: Path) -> None:
        """Regression: non-dict environment should use default Environment."""
        raw = {
            "version": "1",
            "features": [],
            "environment": "not a dict",
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.environment.python_version == ""

    def test_non_dict_stats_falls_back_to_default(self, tmp_path: Path) -> None:
        """Regression: non-dict stats should use default TraceStats."""
        raw = {
            "version": "1",
            "features": [],
            "environment": {},
            "stats": "not a dict",
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.stats.total_features == 0

    def test_non_string_created_at_skipped(self, tmp_path: Path) -> None:
        """Regression: non-string created_at should not crash datetime parsing."""
        raw = {
            "version": "1",
            "features": [],
            "environment": {},
            "stats": {},
            "created_at": 12345,
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        # Should fall back to default datetime, not crash
        assert loaded.created_at is not None

    def test_non_string_start_time_skipped(self, tmp_path: Path) -> None:
        """Regression: non-string start_time should not crash datetime parsing."""
        raw = {
            "version": "1",
            "features": [],
            "environment": {},
            "stats": {"start_time": 12345, "end_time": True},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        # Should not crash; falls back to default (None)
        assert loaded.stats.start_time is None
        assert loaded.stats.end_time is None


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

    def test_structured_log_roundtrip(self, tmp_path: Path) -> None:
        step = Step(
            keyword="Given",
            name="step with logs",
            status=STATUS_PASSED,
            logs=[
                {"level": "info", "message": "started", "timestamp": "2025-01-01T10:00:00"},
                {"level": "error", "message": "failed", "timestamp": "2025-01-01T10:00:01"},
            ],
        )
        scenario = Scenario(name="S", status=STATUS_PASSED, steps=[step])
        trace = Trace(features=[Feature(name="F", status=STATUS_PASSED, scenarios=[scenario])])
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        loaded = Serializer.load(path)
        loaded_step = loaded.features[0].scenarios[0].steps[0]
        assert len(loaded_step.logs) == 2
        assert isinstance(loaded_step.logs[0], dict)
        assert loaded_step.logs[0]["level"] == "info"
        assert loaded_step.logs[0]["message"] == "started"
        assert loaded_step.logs[1]["level"] == "error"
        assert loaded_step.logs[1]["message"] == "failed"

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

    def test_null_list_fields_preserve_defaults(self, tmp_path: Path) -> None:
        """Regression: JSON null for list/dict fields should not become None."""
        trace = Trace()
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        # Manually inject null values for list/dict fields
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        data["features"] = None
        data["environment"]["env_vars"] = None
        data["stats"]["by_status"] = None
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features == []
        assert loaded.environment.env_vars == {}
        assert loaded.stats.by_status == {}

    def test_null_steps_and_artifacts_preserve_defaults(self, tmp_path: Path) -> None:
        """Regression: null steps/artifacts/logs should not become None."""
        raw = {
            "version": "1",
            "features": [
                {
                    "name": "F",
                    "tags": None,
                    "scenarios": None,
                }
            ],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        f = loaded.features[0]
        assert f.scenarios == []
        assert f.tags == []

    def test_null_step_fields_preserve_defaults(self, tmp_path: Path) -> None:
        """Regression: null artifacts/logs in step should not become None."""
        raw = {
            "version": "1",
            "features": [
                {
                    "name": "F",
                    "scenarios": [
                        {
                            "name": "S",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "artifacts": None,
                                    "logs": None,
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        step = loaded.features[0].scenarios[0].steps[0]
        assert step.artifacts == []
        assert step.logs == []

    def test_null_version_preserves_default(self, tmp_path: Path) -> None:
        """Regression: null version field should default to '1'."""
        raw = {
            "version": None,
            "features": [],
            "environment": {},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.version == "1"

    def test_examples_roundtrip(self, tmp_path: Path) -> None:
        """Regression: examples field was not serialized/deserialized."""
        scenario = Scenario(
            name="Outline",
            is_outline=True,
            examples=DataTable(
                headings=["x", "y"],
                rows=[["1", "2"], ["3", "4"]],
            ),
        )
        trace = Trace(features=[Feature(name="F", scenarios=[scenario])])
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        # Verify examples is in the JSON
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["features"][0]["scenarios"][0]["examples"] is not None
        assert data["features"][0]["scenarios"][0]["examples"]["headings"] == ["x", "y"]
        # Verify roundtrip
        loaded = Serializer.load(path)
        s = loaded.features[0].scenarios[0]
        assert s.examples is not None
        assert s.examples.headings == ["x", "y"]
        assert s.examples.rows == [["1", "2"], ["3", "4"]]


def test_non_numeric_duration_does_not_crash(tmp_path: Path) -> None:
    """Regression: non-numeric duration in JSON should not crash or leak type."""
    raw = {
        "version": "1",
        "features": [
            {
                "name": "F",
                "status": "passed",
                "duration": "N/A",
                "scenarios": [
                    {
                        "name": "S",
                        "status": "passed",
                        "duration": "fast",
                        "steps": [
                            {
                                "keyword": "Given",
                                "name": "step",
                                "status": "passed",
                                "duration": "slow",
                            }
                        ],
                    }
                ],
            }
        ],
        "environment": {},
        "stats": {
            "duration": "unknown",
            "slowest_step_duration": "fastest",
            "avg_step_duration": "average",
        },
    }
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = Serializer.load(path)
    assert loaded.features[0].duration == 0.0
    assert loaded.features[0].scenarios[0].duration == 0.0
    assert loaded.features[0].scenarios[0].steps[0].duration == 0.0
    assert loaded.stats.duration == 0.0
    assert loaded.stats.slowest_step_duration == 0.0
    assert loaded.stats.avg_step_duration == 0.0


class TestNonListDictFieldTypes:
    """Regression tests for Bug 26: serializer must validate list/dict field types.

    If a trace JSON file has non-list values for list fields (e.g. ``"tags": "smoke"``
    instead of ``"tags": ["smoke"]``), the deserialization must not assign the wrong
    type to the model field.  Non-dict values for dict fields (e.g. ``"by_status": "passed"``)
    must also be rejected to prevent crashes like ``str.get()``.
    """

    def test_tags_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["tags"] = "smoke"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].tags == []

    def test_tags_as_int_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["tags"] = 42
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].tags == []

    def test_scenario_tags_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["tags"] = "smoke"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].tags == []

    def test_by_status_as_string_coerced_to_empty_dict(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["stats"]["by_status"] = "passed"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.stats.by_status == {}
        assert loaded.stats.passed == 0

    def test_by_status_as_int_coerced_to_empty_dict(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["stats"]["by_status"] = 5
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.stats.by_status == {}

    def test_env_vars_as_string_coerced_to_empty_dict(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["environment"]["env_vars"] = "PATH=/usr/bin"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.environment.env_vars == {}

    def test_scenarios_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"] = "not a list"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios == []

    def test_steps_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"] = "not a list"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].steps == []

    def test_artifacts_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "artifacts": "not a list"}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].steps[0].artifacts == []

    def test_logs_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "logs": "not a list"}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].steps[0].logs == []

    def test_headings_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "table": {"headings": "not a list", "rows": []}}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].steps[0].table is not None
        assert loaded.features[0].scenarios[0].steps[0].table.headings == []

    def test_rows_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "table": {"headings": [], "rows": "not a list"}}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].steps[0].table is not None
        assert loaded.features[0].scenarios[0].steps[0].table.rows == []

    def test_features_as_string_coerced_to_empty_list(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"] = "not a list"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features == []

    def test_is_outline_as_string_coerced_to_bool(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["is_outline"] = "yes"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].is_outline is True

    def test_is_outline_as_empty_string_coerced_to_false(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["is_outline"] = ""
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].scenarios[0].is_outline is False

    def test_environment_as_string_coerced_to_empty(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["environment"] = "not a dict"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.environment.python_version == ""

    def test_stats_as_string_coerced_to_empty(self, tmp_path: Path) -> None:
        raw = _minimal_trace()
        raw["stats"] = "not a dict"
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.stats.total_features == 0


def _minimal_trace() -> dict[str, Any]:
    """Return a minimal valid trace dict for testing."""
    return {
        "version": "1",
        "created_at": "2024-01-01T00:00:00",
        "features": [
            {
                "name": "Feature",
                "status": "passed",
                "duration": 1.0,
                "scenarios": [
                    {
                        "name": "Scenario",
                        "status": "passed",
                        "duration": 0.5,
                        "steps": [],
                    }
                ],
            }
        ],
        "environment": {},
        "stats": {},
    }


class TestIntFieldCoercion:
    """Regression tests for Bug 31: int fields must coerce non-int types."""

    def test_environment_int_fields_from_string(self, tmp_path: Path) -> None:
        """cpu_count and memory_mb as strings should coerce to int."""
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {
                "cpu_count": "4",
                "memory_mb": "8192",
            },
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        trace = Serializer.load(path)
        assert trace.environment.cpu_count == 4
        assert isinstance(trace.environment.cpu_count, int)
        assert trace.environment.memory_mb == 8192
        assert isinstance(trace.environment.memory_mb, int)

    def test_environment_int_fields_from_invalid(self, tmp_path: Path) -> None:
        """cpu_count and memory_mb as invalid types should fall back to 0."""
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {
                "cpu_count": "not_a_number",
                "memory_mb": None,
            },
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        trace = Serializer.load(path)
        assert trace.environment.cpu_count == 0
        assert trace.environment.memory_mb == 0

    def test_stats_int_fields_from_string(self, tmp_path: Path) -> None:
        """Stats int fields as strings should coerce to int."""
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {},
            "stats": {
                "total_features": "3",
                "total_scenarios": "10",
                "total_steps": "25",
                "total_artifacts": "5",
                "total_screenshots": "2",
                "total_logs": "8",
            },
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        trace = Serializer.load(path)
        assert trace.stats.total_features == 3
        assert isinstance(trace.stats.total_features, int)
        assert trace.stats.total_scenarios == 10
        assert isinstance(trace.stats.total_scenarios, int)
        assert trace.stats.total_steps == 25
        assert isinstance(trace.stats.total_steps, int)
        assert trace.stats.total_artifacts == 5
        assert isinstance(trace.stats.total_artifacts, int)
        assert trace.stats.total_screenshots == 2
        assert isinstance(trace.stats.total_screenshots, int)
        assert trace.stats.total_logs == 8
        assert isinstance(trace.stats.total_logs, int)

    def test_stats_int_fields_from_invalid(self, tmp_path: Path) -> None:
        """Stats int fields as invalid types should fall back to 0."""
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {},
            "stats": {
                "total_features": "abc",
                "total_scenarios": None,
                "total_steps": [],
            },
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        trace = Serializer.load(path)
        assert trace.stats.total_features == 0
        assert trace.stats.total_scenarios == 0
        assert trace.stats.total_steps == 0

    def test_by_status_string_values_coerced_to_int(self, tmp_path: Path) -> None:
        """Regression: ``by_status`` dict values were not converted to int
        during deserialization, causing ``TypeError`` in ``pass_rate``
        when values were strings like ``"1"`` instead of ``1``.
        """
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {},
            "stats": {
                "total_features": 1,
                "total_scenarios": 2,
                "total_steps": 4,
                "by_status": {"passed": "2", "failed": "1"},
            },
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        trace = Serializer.load(path)
        assert isinstance(trace.stats.by_status["passed"], int)
        assert isinstance(trace.stats.by_status["failed"], int)
        assert trace.stats.by_status["passed"] == 2
        assert trace.stats.by_status["failed"] == 1
        # pass_rate should not raise TypeError
        _ = trace.stats.pass_rate

    def test_step_text_non_string_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string step text was stored as-is, breaking
        JSON serialization. Now coerced to string."""
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "text": 42}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        step = loaded.features[0].scenarios[0].steps[0]
        assert step.text == "42"
        assert isinstance(step.text, str)

    def test_artifact_text_non_string_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string artifact text was stored as-is."""
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "artifacts": [{"text": 99}]}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        artifact = loaded.features[0].scenarios[0].steps[0].artifacts[0]
        assert artifact.text == "99"
        assert isinstance(artifact.text, str)

    def test_tags_non_string_items_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string tag items were stored as-is."""
        raw = _minimal_trace()
        raw["features"][0]["tags"] = [1, True, "smoke"]
        raw["features"][0]["scenarios"][0]["tags"] = [42, "fast"]
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.features[0].tags == ["1", "True", "smoke"]
        assert loaded.features[0].scenarios[0].tags == ["42", "fast"]

    def test_table_headings_non_string_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string table headings were stored as-is."""
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "table": {"headings": [1, True], "rows": [[2, 3]]}}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        table = loaded.features[0].scenarios[0].steps[0].table
        assert table is not None
        assert table.headings == ["1", "True"]
        assert table.rows == [["2", "3"]]

    def test_env_vars_non_string_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string env_vars values were stored as-is."""
        data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {"env_vars": {"PORT": 8080, "DEBUG": True}},
            "stats": {},
        }
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = Serializer.load(path)
        assert loaded.environment.env_vars["PORT"] == "8080"
        assert loaded.environment.env_vars["DEBUG"] == "True"

    def test_logs_non_string_non_dict_coerced(self, tmp_path: Path) -> None:
        """Regression: non-string, non-dict log items were stored as-is.
        Now coerced to string; dicts and strings preserved."""
        raw = _minimal_trace()
        raw["features"][0]["scenarios"][0]["steps"].append(
            {"keyword": "Given", "name": "step", "logs": [42, "hello", {"level": "info"}]}
        )
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = Serializer.load(path)
        logs = loaded.features[0].scenarios[0].steps[0].logs
        assert logs[0] == "42"
        assert logs[1] == "hello"
        assert isinstance(logs[2], dict)

    def test_save_sanitizes_nan_duration(self, tmp_path: Path) -> None:
        """Regression: NaN float values in trace data are sanitized to 0.0
        instead of producing invalid JSON (NaN token) or crashing."""
        trace = make_trace()
        trace.features[0].scenarios[0].duration = float("nan")
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["scenarios"][0]["duration"] == 0.0

    def test_save_sanitizes_infinity_duration(self, tmp_path: Path) -> None:
        """Regression: Infinity in trace data is sanitized to 0.0."""
        trace = make_trace()
        trace.features[0].scenarios[0].duration = float("inf")
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["scenarios"][0]["duration"] == 0.0
