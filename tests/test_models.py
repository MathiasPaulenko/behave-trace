"""Tests for behave_trace.models."""

from __future__ import annotations

from datetime import datetime

from behave_trace.models import (
    ARTIFACT_DOM,
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    STATUS_UNDEFINED,
    STATUS_UNTESTED,
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
    as_dict,
    normalize_status,
)

# ---------------------------------------------------------------------------
# normalize_status
# ---------------------------------------------------------------------------


class TestNormalizeStatus:
    def test_string_passed(self) -> None:
        assert normalize_status("passed") == STATUS_PASSED

    def test_string_failed(self) -> None:
        assert normalize_status("failed") == STATUS_FAILED

    def test_string_skipped(self) -> None:
        assert normalize_status("skipped") == STATUS_SKIPPED

    def test_string_undefined(self) -> None:
        assert normalize_status("undefined") == STATUS_UNDEFINED

    def test_none_returns_untested(self) -> None:
        assert normalize_status(None) == STATUS_UNTESTED

    def test_uppercase_string(self) -> None:
        assert normalize_status("PASSED") == STATUS_PASSED

    def test_unknown_returns_untested(self) -> None:
        assert normalize_status("foobar") == STATUS_UNTESTED

    def test_enum_like_object(self) -> None:
        class FakeStatus:
            name = "passed"

        assert normalize_status(FakeStatus()) == STATUS_PASSED


# ---------------------------------------------------------------------------
# Artifact properties
# ---------------------------------------------------------------------------


class TestArtifact:
    def test_is_image_png(self) -> None:
        a = Artifact(type=ARTIFACT_SCREENSHOT, mime_type="image/png")
        assert a.is_image is True

    def test_is_image_not_image(self) -> None:
        a = Artifact(type=ARTIFACT_DOM, mime_type="text/html")
        assert a.is_image is False

    def test_is_text_html(self) -> None:
        a = Artifact(type=ARTIFACT_DOM, mime_type="text/html")
        assert a.is_text is True

    def test_is_text_json(self) -> None:
        a = Artifact(type=ARTIFACT_TEXT, mime_type="application/json")
        assert a.is_text is True

    def test_is_text_not_text(self) -> None:
        a = Artifact(type=ARTIFACT_SCREENSHOT, mime_type="image/png")
        assert a.is_text is False

    def test_to_dict(self) -> None:
        a = Artifact(
            type=ARTIFACT_SCREENSHOT,
            name="shot.png",
            mime_type="image/png",
            data_base64="abc",
        )
        d = a.to_dict()
        assert d["type"] == ARTIFACT_SCREENSHOT
        assert d["name"] == "shot.png"
        assert d["mime_type"] == "image/png"
        assert d["data_base64"] == "abc"
        assert d["text"] is None


# ---------------------------------------------------------------------------
# Step properties and to_dict
# ---------------------------------------------------------------------------


class TestStep:
    def test_has_screenshot_true(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_SCREENSHOT)])
        assert step.has_screenshot is True

    def test_has_screenshot_false(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_DOM)])
        assert step.has_screenshot is False

    def test_has_dom_true(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_DOM)])
        assert step.has_dom is True

    def test_has_dom_false(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_SCREENSHOT)])
        assert step.has_dom is False

    def test_to_dict_includes_has_screenshot(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_SCREENSHOT)])
        d = step.to_dict()
        assert d["has_screenshot"] is True
        assert d["has_dom"] is False

    def test_to_dict_includes_has_dom(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_DOM)])
        d = step.to_dict()
        assert d["has_dom"] is True
        assert d["has_screenshot"] is False

    def test_to_dict_includes_all_fields(self) -> None:
        step = Step(
            keyword="Given",
            name="I do something",
            status=STATUS_PASSED,
            duration=0.5,
            location="steps.py:10",
            text="some text",
            table=DataTable(headings=["a"], rows=[["1"]]),
            error=ErrorInfo(message="err"),
            artifacts=[Artifact(type=ARTIFACT_SCREENSHOT)],
            logs=["log1"],
        )
        d = step.to_dict()
        assert d["keyword"] == "Given"
        assert d["name"] == "I do something"
        assert d["status"] == STATUS_PASSED
        assert d["duration"] == 0.5
        assert d["location"] == "steps.py:10"
        assert d["text"] == "some text"
        assert d["table"] == {"headings": ["a"], "rows": [["1"]]}
        assert d["error"] == {"message": "err", "traceback": "", "exception_type": ""}
        assert len(d["artifacts"]) == 1
        assert d["logs"] == ["log1"]

    def test_to_dict_with_none_table_and_error(self) -> None:
        step = Step(keyword="Given", name="step")
        d = step.to_dict()
        assert d["table"] is None
        assert d["error"] is None


# ---------------------------------------------------------------------------
# Scenario properties and to_dict
# ---------------------------------------------------------------------------


class TestScenario:
    def test_step_count(self) -> None:
        scenario = Scenario(
            name="S",
            steps=[Step(keyword="Given", name="a"), Step(keyword="Then", name="b")],
        )
        assert scenario.step_count == 2

    def test_passed_steps(self) -> None:
        scenario = Scenario(
            name="S",
            steps=[
                Step(keyword="Given", name="a", status=STATUS_PASSED),
                Step(keyword="Then", name="b", status=STATUS_FAILED),
            ],
        )
        assert scenario.passed_steps == 1

    def test_failed_steps(self) -> None:
        scenario = Scenario(
            name="S",
            steps=[
                Step(keyword="Given", name="a", status=STATUS_PASSED),
                Step(keyword="Then", name="b", status=STATUS_FAILED),
            ],
        )
        assert scenario.failed_steps == 1

    def test_to_dict_includes_computed(self) -> None:
        scenario = Scenario(
            name="S",
            steps=[Step(keyword="Given", name="a", status=STATUS_PASSED)],
        )
        d = scenario.to_dict()
        assert d["step_count"] == 1
        assert d["passed_steps"] == 1
        assert d["failed_steps"] == 0

    def test_to_dict_includes_background(self) -> None:
        bg = Background(name="bg", steps=[Step(keyword="Given", name="bg step")])
        scenario = Scenario(name="S", background=bg)
        d = scenario.to_dict()
        assert d["background"] is not None
        assert d["background"]["name"] == "bg"


# ---------------------------------------------------------------------------
# Feature properties and to_dict
# ---------------------------------------------------------------------------


class TestFeature:
    def test_scenario_count(self) -> None:
        feature = Feature(name="F", scenarios=[Scenario(name="S1"), Scenario(name="S2")])
        assert feature.scenario_count == 2

    def test_to_dict_includes_scenario_count(self) -> None:
        feature = Feature(name="F", scenarios=[Scenario(name="S1")])
        d = feature.to_dict()
        assert d["scenario_count"] == 1


# ---------------------------------------------------------------------------
# Trace overall_status and to_dict
# ---------------------------------------------------------------------------


class TestTrace:
    def test_overall_status_failed(self) -> None:
        trace = Trace(
            features=[
                Feature(name="F1", status=STATUS_PASSED),
                Feature(name="F2", status=STATUS_FAILED),
            ],
        )
        assert trace.overall_status == STATUS_FAILED

    def test_overall_status_passed(self) -> None:
        trace = Trace(features=[Feature(name="F1", status=STATUS_PASSED)])
        assert trace.overall_status == STATUS_PASSED

    def test_overall_status_untested_empty(self) -> None:
        trace = Trace(features=[])
        assert trace.overall_status == STATUS_UNTESTED

    def test_overall_status_skipped(self) -> None:
        trace = Trace(features=[Feature(name="F1", status=STATUS_SKIPPED)])
        assert trace.overall_status == STATUS_SKIPPED

    def test_overall_status_undefined(self) -> None:
        trace = Trace(features=[Feature(name="F1", status=STATUS_UNDEFINED)])
        assert trace.overall_status == STATUS_UNDEFINED

    def test_to_dict_includes_overall_status(self) -> None:
        trace = Trace(features=[Feature(name="F1", status=STATUS_FAILED)])
        d = trace.to_dict()
        assert d["overall_status"] == STATUS_FAILED

    def test_to_dict_includes_version_and_created_at(self) -> None:
        trace = Trace(version="1", created_at=datetime(2025, 1, 1, 12, 0, 0))
        d = trace.to_dict()
        assert d["version"] == "1"
        assert d["created_at"] == "2025-01-01T12:00:00"

    def test_to_dict_includes_environment_and_stats(self) -> None:
        env = Environment(python_version="3.12", platform="linux")
        stats = TraceStats(total_features=1, total_scenarios=2)
        trace = Trace(environment=env, stats=stats)
        d = trace.to_dict()
        assert d["environment"]["python_version"] == "3.12"
        assert d["stats"]["total_features"] == 1
        assert d["stats"]["total_scenarios"] == 2


# ---------------------------------------------------------------------------
# as_dict
# ---------------------------------------------------------------------------


class TestAsDict:
    def test_delegates_to_to_dict(self) -> None:
        step = Step(keyword="Given", name="step", artifacts=[Artifact(type=ARTIFACT_SCREENSHOT)])
        d = as_dict(step)
        assert d["has_screenshot"] is True

    def test_dataclass_without_to_dict(self) -> None:
        error = ErrorInfo(message="err", traceback="tb", exception_type="ValueError")
        d = as_dict(error)
        assert d == {"message": "err", "traceback": "tb", "exception_type": "ValueError"}

    def test_list_of_dataclasses(self) -> None:
        artifacts = [Artifact(type=ARTIFACT_SCREENSHOT), Artifact(type=ARTIFACT_DOM)]
        result = as_dict(artifacts)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == ARTIFACT_SCREENSHOT

    def test_dict_of_values(self) -> None:
        data = {"key": ErrorInfo(message="err"), "count": 5}
        result = as_dict(data)
        assert result["key"] == {"message": "err", "traceback": "", "exception_type": ""}
        assert result["count"] == 5

    def test_datetime(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0)
        assert as_dict(dt) == "2025-01-01T12:00:00"

    def test_primitive(self) -> None:
        assert as_dict(42) == 42
        assert as_dict("hello") == "hello"
        assert as_dict(None) is None

    def test_dataclass_with_datetime_field(self) -> None:
        stats = TraceStats(start_time=datetime(2025, 1, 1, 12, 0, 0))
        d = as_dict(stats)
        assert d["start_time"] == "2025-01-01T12:00:00"
