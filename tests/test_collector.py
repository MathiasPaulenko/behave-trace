"""Tests for behave_trace.collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from behave_trace.collector import Collector
from behave_trace.models import (
    ARTIFACT_DOM,
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    STATUS_FAILED,
    STATUS_PASSED,
    Artifact,
)

# ---------------------------------------------------------------------------
# Stub helpers — minimal objects that mimic Behave's internal structure
# ---------------------------------------------------------------------------


@dataclass
class StubStep:
    keyword: str = "Given"
    name: str = "do something"
    status: str = "passed"
    duration: float = 0.1
    location: str = "steps.py:10"
    text: str | None = None
    table: Any = None
    error_message: str = ""
    exception: Any = None
    exc_traceback: str = ""
    embeddings: list[Any] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


@dataclass
class StubTable:
    headings: list[str] = field(default_factory=lambda: ["col1", "col2"])
    rows: list[Any] = field(default_factory=list)


@dataclass
class StubRow:
    cells: list[str] = field(default_factory=lambda: ["a", "b"])


@dataclass
class StubEmbedding:
    mime_type: str = ""
    name: str = ""
    data: str = ""


@dataclass
class StubScenario:
    name: str = "Test scenario"
    status: str = "passed"
    duration: float = 0.5
    description: list[str] = field(default_factory=list)
    location: str = "feature.feature:5"
    tags: list[str] = field(default_factory=list)
    type: str = "scenario"


@dataclass
class StubBackground:
    name: str = ""
    keyword: str = "Background"
    location: str = "feature.feature:3"
    steps: list[Any] = field(default_factory=list)


@dataclass
class StubFeature:
    name: str = "Test feature"
    status: str = "passed"
    duration: float = 1.0
    description: list[str] = field(default_factory=list)
    location: str = "feature.feature:1"
    tags: list[str] = field(default_factory=list)
    background: Any = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCaptureEnvironment:
    def test_environment_captured(self) -> None:
        c = Collector()
        env = c.trace.environment
        assert env.python_version != ""
        assert env.platform != ""
        assert env.hostname != ""

    def test_trace_has_start_time(self) -> None:
        c = Collector()
        assert c.trace.stats.start_time is not None


class TestOnFeature:
    def test_creates_feature_with_name(self) -> None:
        c = Collector()
        f = c.on_feature(StubFeature(name="My Feature"))
        assert f.name == "My Feature"
        assert f in c.trace.features

    def test_extracts_description_and_tags(self) -> None:
        c = Collector()
        f = c.on_feature(
            StubFeature(
                name="F",
                description=["line1", "line2"],
                tags=["@smoke", "@wip"],
            )
        )
        assert f.description == "line1\nline2"
        assert f.tags == ["@smoke", "@wip"]

    def test_extracts_location(self) -> None:
        c = Collector()
        f = c.on_feature(StubFeature(name="F", location="features/test.feature:1"))
        assert f.location == "features/test.feature:1"

    def test_creates_background(self) -> None:
        c = Collector()
        bg = StubBackground(name="bg", steps=[StubStep(keyword="Given", name="bg step")])
        f = c.on_feature(StubFeature(name="F", background=bg))
        assert f.background is not None
        assert f.background.name == "bg"
        assert len(f.background.steps) == 1
        assert f.background.steps[0].name == "bg step"

    def test_feature_end_sets_status_and_duration(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_feature_end(StubFeature(name="F", status="failed", duration=2.5))
        assert c.trace.features[0].status == STATUS_FAILED
        assert c.trace.features[0].duration == 2.5


class TestOnScenario:
    def test_creates_scenario_associated_to_feature(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        s = c.on_scenario(StubScenario(name="S"))
        assert s.name == "S"
        assert s in c.trace.features[0].scenarios

    def test_scenario_has_feature_name(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="My Feature"))
        s = c.on_scenario(StubScenario(name="S"))
        assert s.feature_name == "My Feature"

    def test_scenario_inherits_background(self) -> None:
        c = Collector()
        bg = StubBackground(name="bg", steps=[StubStep(keyword="Given", name="bg")])
        c.on_feature(StubFeature(name="F", background=bg))
        s = c.on_scenario(StubScenario(name="S"))
        assert s.background is not None
        assert s.background.name == "bg"

    def test_scenario_end_sets_status_and_duration(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_scenario_end(StubScenario(name="S", status="failed", duration=1.5))
        assert c.trace.features[0].scenarios[0].status == STATUS_FAILED
        assert c.trace.features[0].scenarios[0].duration == 1.5

    def test_outline_detected(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        s = c.on_scenario(StubScenario(name="S", type="scenario_outline"))
        assert s.is_outline is True

    def test_rule_name_captured(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))

        @dataclass
        class StubRule:
            name: str = "My Rule"

        c.on_rule(StubRule())
        s = c.on_scenario(StubScenario(name="S"))
        assert s.rule_name == "My Rule"


class TestOnStep:
    def test_creates_step_with_status_and_duration(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        step = c.on_step(StubStep(keyword="Given", name="step", status="passed", duration=0.3))
        assert step is not None
        assert step.status == STATUS_PASSED
        assert step.duration == 0.3
        assert step in c.trace.features[0].scenarios[0].steps

    def test_step_without_scenario_returns_none(self) -> None:
        c = Collector()
        step = c.on_step(StubStep())
        assert step is None

    def test_step_with_error(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        step = c.on_step(
            StubStep(
                keyword="Then",
                name="fail",
                status="failed",
                error_message="Assertion failed",
                exception=ValueError("bad value"),
            )
        )
        assert step is not None
        assert step.error is not None
        assert step.error.message == "Assertion failed"
        assert step.error.exception_type == "ValueError"

    def test_step_with_table(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        table = StubTable(headings=["a", "b"], rows=[StubRow(cells=["1", "2"])])
        step = c.on_step(StubStep(keyword="Given", name="step", table=table))
        assert step is not None
        assert step.table is not None
        assert step.table.headings == ["a", "b"]
        assert step.table.rows == [["1", "2"]]

    def test_step_with_logs(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        step = c.on_step(StubStep(keyword="Given", name="step", log=["line1", "line2"]))
        assert step is not None
        assert step.logs == ["line1", "line2"]


class TestMakeArtifact:
    def test_image_png_maps_to_screenshot(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding(mime_type="image/png", data="abc"))
        assert a is not None
        assert a.type == ARTIFACT_SCREENSHOT

    def test_text_html_maps_to_dom(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding(mime_type="text/html", data="abc"))
        assert a is not None
        assert a.type == ARTIFACT_DOM

    def test_name_screenshot_maps_to_screenshot(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding(name="screenshot_1.png", data="abc"))
        assert a is not None
        assert a.type == ARTIFACT_SCREENSHOT

    def test_name_dom_maps_to_dom(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding(name="dom_snapshot.html", data="abc"))
        assert a is not None
        assert a.type == ARTIFACT_DOM

    def test_empty_embedding_returns_none(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding())
        assert a is None

    def test_text_fallback(self) -> None:
        c = Collector()
        a = c._make_artifact(StubEmbedding(mime_type="text/plain", name="log.txt", data="abc"))
        assert a is not None
        assert a.type == ARTIFACT_TEXT

    def test_non_string_name_does_not_crash(self) -> None:
        """Regression: non-string name attribute should not crash _make_artifact."""

        class WeirdEmbedding:
            mime_type = "text/plain"
            name = 42
            data = "abc"

        c = Collector()
        a = c._make_artifact(WeirdEmbedding())
        assert a is not None
        assert a.type == ARTIFACT_TEXT

    def test_non_string_mime_type_does_not_crash(self) -> None:
        """Regression: non-string mime_type should not crash _make_artifact."""

        class WeirdEmbedding:
            mime_type = None
            name = "screenshot_1.png"
            data = "abc"

        c = Collector()
        a = c._make_artifact(WeirdEmbedding())
        assert a is not None
        assert a.type == ARTIFACT_SCREENSHOT


class TestAttach:
    def test_attach_buffers_then_flushes_on_step(self) -> None:
        """attach() before on_step() buffers the artifact; on_step flushes it."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.attach(Artifact(type=ARTIFACT_SCREENSHOT, name="shot.png", mime_type="image/png"))
        c.on_step(StubStep(keyword="Given", name="step"))
        step = c.trace.features[0].scenarios[0].steps[0]
        assert len(step.artifacts) == 1
        assert step.artifacts[0].type == ARTIFACT_SCREENSHOT

    def test_attach_after_step_buffers_for_next_step(self) -> None:
        """attach() after on_step() buffers for the next step, not the previous one."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(keyword="Given", name="step1"))
        c.attach(Artifact(type=ARTIFACT_SCREENSHOT, name="shot.png", mime_type="image/png"))
        c.on_step(StubStep(keyword="When", name="step2"))
        step1 = c.trace.features[0].scenarios[0].steps[0]
        step2 = c.trace.features[0].scenarios[0].steps[1]
        assert len(step1.artifacts) == 0
        assert len(step2.artifacts) == 1

    def test_attach_without_scenario_noop(self) -> None:
        c = Collector()
        c.attach(Artifact(type=ARTIFACT_SCREENSHOT))
        # Should not raise


class TestLog:
    def test_log_buffers_then_flushes_on_step(self) -> None:
        """log() before on_step() buffers; on_step flushes it onto the step."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.log("something happened")
        c.on_step(StubStep(keyword="Given", name="step"))
        step = c.trace.features[0].scenarios[0].steps[0]
        assert len(step.logs) == 1
        entry = step.logs[0]
        assert isinstance(entry, dict)
        assert entry["message"] == "something happened"
        assert entry["level"] == "info"
        assert "timestamp" in entry

    def test_log_with_level(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.log("oops", level="error")
        c.on_step(StubStep(keyword="Given", name="step"))
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.logs[0]["level"] == "error"

    def test_log_level_normalization(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.log("warn", level="WARN")
        c.on_step(StubStep(keyword="Given", name="step"))
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.logs[0]["level"] == "warning"

    def test_log_without_step_noop(self) -> None:
        c = Collector()
        c.log("test")
        # Should not raise


class TestFinalize:
    def test_finalize_sets_end_time(self) -> None:
        c = Collector()
        trace = c.finalize()
        assert trace.stats.end_time is not None

    def test_compute_stats_totals(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F1", status="passed", duration=1.0))
        c.on_scenario(StubScenario(name="S1", status="passed", duration=0.5))
        c.on_step(StubStep(keyword="Given", name="a", status="passed", duration=0.2))
        c.on_step(StubStep(keyword="Then", name="b", status="passed", duration=0.3))
        c.on_scenario(StubScenario(name="S2", status="failed", duration=0.5))
        c.on_step(StubStep(keyword="Given", name="c", status="passed", duration=0.1))
        c.on_step(StubStep(keyword="Then", name="d", status="failed", duration=0.4))
        c.finalize()

        stats = c.trace.stats
        assert stats.total_features == 1
        assert stats.total_scenarios == 2
        assert stats.total_steps == 4

    def test_compute_stats_by_status(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F1"))
        c.on_scenario(StubScenario(name="S1", status="passed"))
        c.on_scenario_end(StubScenario(name="S1", status="passed"))
        c.on_feature_end(StubFeature(name="F1", status="passed"))
        c.on_feature(StubFeature(name="F2"))
        c.on_scenario(StubScenario(name="S2", status="failed"))
        c.on_scenario_end(StubScenario(name="S2", status="failed"))
        c.on_feature_end(StubFeature(name="F2", status="failed"))
        c.finalize()

        stats = c.trace.stats
        assert stats.by_status.get("passed") == 1
        assert stats.by_status.get("failed") == 1

    def test_compute_stats_slowest_step(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F", status="passed"))
        c.on_scenario(StubScenario(name="S", status="passed"))
        c.on_step(StubStep(keyword="Given", name="fast", duration=0.1))
        c.on_step(StubStep(keyword="Then", name="slow", duration=2.5))
        c.finalize()

        stats = c.trace.stats
        assert stats.slowest_step_duration == 2.5
        assert "slow" in stats.slowest_step_name

    def test_compute_stats_artifacts_and_logs(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F", status="passed"))
        c.on_scenario(StubScenario(name="S", status="passed"))
        c.on_step(
            StubStep(
                keyword="Given",
                name="step",
                duration=0.1,
                embeddings=[StubEmbedding(mime_type="image/png", data="abc")],
                log=["log1", "log2"],
            )
        )
        c.finalize()

        stats = c.trace.stats
        assert stats.total_artifacts == 1
        assert stats.total_screenshots == 1
        assert stats.total_logs == 2

    def test_compute_stats_avg_duration(self) -> None:
        c = Collector()
        c.on_feature(StubFeature(name="F", status="passed"))
        c.on_scenario(StubScenario(name="S", status="passed"))
        c.on_step(StubStep(keyword="Given", name="a", duration=0.2))
        c.on_step(StubStep(keyword="Then", name="b", duration=0.4))
        c.finalize()

        stats = c.trace.stats
        assert abs(stats.avg_step_duration - 0.3) < 1e-9

    def test_compute_stats_empty_trace(self) -> None:
        c = Collector()
        c.finalize()

        stats = c.trace.stats
        assert stats.total_features == 0
        assert stats.total_scenarios == 0
        assert stats.total_steps == 0
        assert stats.slowest_step_duration == 0.0
        assert stats.avg_step_duration == 0.0


class TestNonStringAttributes:
    """Regression tests for non-string attributes from Behave objects."""

    def test_non_string_feature_name(self) -> None:
        """Regression: non-string feature name should not crash or leak type."""
        c = Collector()
        c.on_feature(StubFeature(name=42))  # type: ignore[arg-type]
        assert c.trace.features[0].name == "42"

    def test_non_string_scenario_name(self) -> None:
        """Regression: non-string scenario name should not crash or leak type."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name=99))  # type: ignore[arg-type]
        assert c.trace.features[0].scenarios[0].name == "99"

    def test_non_string_step_name(self) -> None:
        """Regression: non-string step name should not crash or leak type."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(name=123))  # type: ignore[arg-type]
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.name == "123"

    def test_non_string_step_keyword(self) -> None:
        """Regression: non-string keyword should not crash on .strip()."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(keyword=42))  # type: ignore[arg-type]
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.keyword == "42"

    def test_non_string_rule_name(self) -> None:
        """Regression: non-string rule name should not crash."""
        c = Collector()

        class WeirdRule:
            name = 77  # type: ignore[assignment]

        c.on_rule(WeirdRule())
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        assert c.trace.features[0].scenarios[0].rule_name == "77"

    def test_non_string_background_name(self) -> None:
        """Regression: non-string background name/keyword should not crash."""
        c = Collector()
        c.on_feature(StubFeature(name="F", background=StubBackground(name=10, keyword=20)))  # type: ignore[arg-type]
        bg = c.trace.features[0].background
        assert bg is not None
        assert bg.name == "10"
        assert bg.keyword == "20"

    def test_non_string_description_items(self) -> None:
        """Regression: non-string items in description list should not crash join."""
        c = Collector()
        c.on_feature(StubFeature(name="F", description=[None, 42, "text"]))  # type: ignore[list-item]
        assert "42" in c.trace.features[0].description
        assert "text" in c.trace.features[0].description

    def test_string_description_not_iterated_as_characters(self) -> None:
        """Regression: when ``description`` is a plain string instead of a
        list, ``"\\n".join(d for d in description)`` iterated characters
        one-by-one, producing garbage like ``"S\\no\\nm\\ne"``.
        """
        c = Collector()
        c.on_feature(StubFeature(name="F", description="Some description"))  # type: ignore[arg-type]
        assert c.trace.features[0].description == "Some description"

    def test_string_description_scenario_not_iterated_as_characters(self) -> None:
        """Regression: same character-iteration bug for scenario descriptions."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S", description="A scenario description"))  # type: ignore[arg-type]
        assert c.trace.features[0].scenarios[0].description == "A scenario description"

    def test_non_numeric_duration_does_not_crash(self) -> None:
        """Regression: non-numeric duration string should not crash float()."""
        c = Collector()
        c.on_feature(StubFeature(duration="N/A"))  # type: ignore[arg-type]
        c.on_feature_end(StubFeature(duration="N/A"))  # type: ignore[arg-type]
        assert c.trace.features[0].duration == 0.0

    def test_non_numeric_step_duration_does_not_crash(self) -> None:
        """Regression: non-numeric step duration should not crash."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(duration="fast"))  # type: ignore[arg-type]
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.duration == 0.0

    def test_non_string_step_text_is_converted(self) -> None:
        """Regression: non-string step text should be safely converted to
        string, not stored as-is which could break JSON serialization."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(text=42))  # type: ignore[arg-type]
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.text == "42"
        assert isinstance(step.text, str)

    def test_none_step_text_stays_none(self) -> None:
        """Ensure that None text stays None, not converted to 'None' string."""
        c = Collector()
        c.on_feature(StubFeature(name="F"))
        c.on_scenario(StubScenario(name="S"))
        c.on_step(StubStep(text=None))
        step = c.trace.features[0].scenarios[0].steps[0]
        assert step.text is None
