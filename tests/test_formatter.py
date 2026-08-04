"""Tests for behave_trace.formatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from behave_trace.formatter import TraceFormatter
from behave_trace.models import (
    ARTIFACT_SCREENSHOT,
    STATUS_PASSED,
    Artifact,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class StubStreamOpener:
    name: str | None = None
    filename: str | None = None
    stream: Any = None


@dataclass
class StubOutput:
    name: str = ""


@dataclass
class StubConfig:
    outputs: list[Any] = field(default_factory=list)


@dataclass
class StubFeature:
    name: str = "Feature"
    status: str = "passed"
    duration: float = 1.0
    description: list[str] = field(default_factory=list)
    location: str = "feature.feature:1"
    tags: list[str] = field(default_factory=list)
    background: Any = None


@dataclass
class StubScenario:
    name: str = "Scenario"
    status: str = "passed"
    duration: float = 0.5
    description: list[str] = field(default_factory=list)
    location: str = "feature.feature:5"
    tags: list[str] = field(default_factory=list)
    type: str = "scenario"


@dataclass
class StubStep:
    keyword: str = "Given"
    name: str = "step"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_formatter(output_path: str = "trace.json") -> TraceFormatter:
    opener = StubStreamOpener(name=output_path)
    config = StubConfig()
    return TraceFormatter(opener, config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveOutputPath:
    def test_from_stream_opener_name(self) -> None:
        opener = StubStreamOpener(name="output.json")
        path = TraceFormatter._resolve_output_path(opener, StubConfig())
        assert path == Path("output.json")

    def test_from_stream_opener_filename(self) -> None:
        opener = StubStreamOpener(name=None, filename="alt.json")
        path = TraceFormatter._resolve_output_path(opener, StubConfig())
        assert path == Path("alt.json")

    def test_from_config_outputs(self) -> None:
        opener = StubStreamOpener()
        config = StubConfig(outputs=[StubOutput(name="from_config.json")])
        path = TraceFormatter._resolve_output_path(opener, config)
        assert path == Path("from_config.json")

    def test_skips_stdout(self) -> None:
        opener = StubStreamOpener()
        config = StubConfig(outputs=[StubOutput(name="<stdout>"), StubOutput(name="real.json")])
        path = TraceFormatter._resolve_output_path(opener, config)
        assert path == Path("real.json")

    def test_fallback_to_trace_json(self) -> None:
        opener = StubStreamOpener()
        path = TraceFormatter._resolve_output_path(opener, StubConfig())
        assert path == Path("trace.json")


class TestFeature:
    def test_calls_collector_on_feature(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="My Feature"))
        assert f._collector.trace.features[0].name == "My Feature"

    def test_stores_behave_feature_ref(self) -> None:
        feat = StubFeature(name="F")
        f = make_formatter()
        f.feature(feat)
        assert f._behave_feature is feat


class TestScenario:
    def test_calls_collector_on_scenario(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        assert f._collector.trace.features[0].scenarios[0].name == "S"

    def test_finalizes_previous_scenario(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        s1 = StubScenario(name="S1", status="passed", duration=0.3)
        f.scenario(s1)
        s2 = StubScenario(name="S2")
        f.scenario(s2)
        # S1 should be finalized with status
        assert f._collector.trace.features[0].scenarios[0].status == STATUS_PASSED
        assert f._collector.trace.features[0].scenarios[0].duration == 0.3
        # S2 should be the current one
        assert f._collector.trace.features[0].scenarios[1].name == "S2"

    def test_stores_behave_scenario_ref(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        s = StubScenario(name="S")
        f.scenario(s)
        assert f._behave_scenario is s


class TestResult:
    def test_calls_collector_on_step(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        f.result(StubStep(keyword="Given", name="do thing", status="passed", duration=0.2))
        steps = f._collector.trace.features[0].scenarios[0].steps
        assert len(steps) == 1
        assert steps[0].name == "do thing"
        assert steps[0].status == STATUS_PASSED


class TestEof:
    def test_finalizes_scenario_and_feature(self) -> None:
        f = make_formatter()
        feat = StubFeature(name="F", status="passed", duration=1.0)
        f.feature(feat)
        scen = StubScenario(name="S", status="passed", duration=0.5)
        f.scenario(scen)
        f.eof()
        assert f._collector.trace.features[0].status == STATUS_PASSED
        assert f._collector.trace.features[0].duration == 1.0
        assert f._collector.trace.features[0].scenarios[0].status == STATUS_PASSED
        assert f._collector.trace.features[0].scenarios[0].duration == 0.5

    def test_clears_refs(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        f.eof()
        assert f._behave_feature is None
        assert f._behave_scenario is None

    def test_eof_without_scenario(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F", status="passed"))
        f.eof()
        assert f._behave_feature is None

    def test_eof_without_feature(self) -> None:
        f = make_formatter()
        f.eof()
        # Should not raise


class TestAttachAndLog:
    def test_attach_delegates_to_collector(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        f.attach(Artifact(type=ARTIFACT_SCREENSHOT, name="shot.png", mime_type="image/png"))
        f.result(StubStep(keyword="Given", name="step"))
        step = f._collector.trace.features[0].scenarios[0].steps[0]
        assert len(step.artifacts) == 1
        assert step.artifacts[0].type == ARTIFACT_SCREENSHOT

    def test_log_delegates_to_collector(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        f.log("test message")
        f.result(StubStep(keyword="Given", name="step"))
        step = f._collector.trace.features[0].scenarios[0].steps[0]
        assert len(step.logs) == 1
        assert isinstance(step.logs[0], dict)
        assert step.logs[0]["message"] == "test message"
        assert step.logs[0]["level"] == "info"

    def test_log_with_level(self) -> None:
        f = make_formatter()
        f.feature(StubFeature(name="F"))
        f.scenario(StubScenario(name="S"))
        f.log("something broke", level="error")
        f.result(StubStep(keyword="Given", name="step"))
        step = f._collector.trace.features[0].scenarios[0].steps[0]
        assert step.logs[0]["level"] == "error"


class TestClose:
    def test_close_calls_finalize_and_save(self, tmp_path: Path) -> None:
        f = make_formatter(str(tmp_path / "trace.json"))
        f.feature(StubFeature(name="F", status="passed", duration=1.0))
        f.scenario(StubScenario(name="S", status="passed", duration=0.5))
        f.result(StubStep(keyword="Given", name="step", status="passed", duration=0.1))
        f.eof()

        with patch("behave_trace.serializer.Serializer.save") as mock_save:
            f.close()
            mock_save.assert_called_once()
            trace_arg = mock_save.call_args[0][0]
            assert trace_arg.stats.total_features == 1
            assert trace_arg.stats.total_steps == 1

    def test_close_writes_file(self, tmp_path: Path) -> None:
        f = make_formatter(str(tmp_path / "trace.json"))
        f.feature(StubFeature(name="F", status="passed"))
        f.scenario(StubScenario(name="S", status="passed"))
        f.result(StubStep(keyword="Given", name="step", status="passed", duration=0.1))
        f.eof()
        f.close()

        assert (tmp_path / "trace.json").exists()


class TestBackgroundAndStep:
    def test_background_is_noop(self) -> None:
        f = make_formatter()
        f.background(MagicMock())
        # Should not raise, no side effects

    def test_step_is_noop(self) -> None:
        f = make_formatter()
        f.step(MagicMock())
        # Should not raise, no side effects

    def test_match_is_noop(self) -> None:
        f = make_formatter()
        f.match(MagicMock())
        # Should not raise, no side effects


class TestCloseSaveError:
    def test_close_handles_save_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression for Bug 30: Serializer.save OSError must not crash close()."""
        f = make_formatter(str(tmp_path / "trace.json"))
        f.feature(StubFeature(name="F", status="passed"))
        f.scenario(StubScenario(name="S", status="passed"))
        f.result(StubStep(keyword="Given", name="step", status="passed", duration=0.1))
        f.eof()

        with patch(
            "behave_trace.serializer.Serializer.save",
            side_effect=OSError("disk full"),
        ):
            f.close()  # Should not raise

        err = capsys.readouterr().err
        assert "cannot write trace file" in err.lower()
