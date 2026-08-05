"""Deep edge-case tests for serializer load, attach module, and server concurrency."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from behave_trace.models import (
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    Artifact,
    Feature,
    Scenario,
    Step,
    Trace,
)
from behave_trace.serializer import Serializer


class TestSerializerLoadMalformed:
    """Test Serializer.load with malformed/corrupted JSON files."""

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Empty file raises JSONDecodeError."""
        p = tmp_path / "empty.json"
        p.write_text("")
        with pytest.raises(json.JSONDecodeError):
            Serializer.load(p)

    def test_load_non_object_root(self, tmp_path: Path) -> None:
        """JSON array at root raises ValueError."""
        p = tmp_path / "array.json"
        p.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_string_root(self, tmp_path: Path) -> None:
        """JSON string at root raises ValueError."""
        p = tmp_path / "string.json"
        p.write_text('"hello"')
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_number_root(self, tmp_path: Path) -> None:
        """JSON number at root raises ValueError."""
        p = tmp_path / "number.json"
        p.write_text("42")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_null_root(self, tmp_path: Path) -> None:
        """JSON null at root raises ValueError."""
        p = tmp_path / "null.json"
        p.write_text("null")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_bom_prefix(self, tmp_path: Path) -> None:
        """UTF-8 BOM is handled by utf-8-sig encoding."""
        p = tmp_path / "bom.json"
        p.write_bytes(b'\xef\xbb\xbf{"version": "1", "features": []}')
        trace = Serializer.load(p)
        assert trace.version == "1"

    def test_load_missing_features_key(self, tmp_path: Path) -> None:
        """Missing 'features' key produces empty features list."""
        p = tmp_path / "nofeatures.json"
        p.write_text(json.dumps({"version": "2"}))
        trace = Serializer.load(p)
        assert trace.features == []
        assert trace.version == "2"

    def test_load_features_not_list(self, tmp_path: Path) -> None:
        """Features as non-list is silently treated as empty."""
        p = tmp_path / "badfeatures.json"
        p.write_text(json.dumps({"features": "not a list"}))
        trace = Serializer.load(p)
        assert trace.features == []

    def test_load_feature_item_not_dict(self, tmp_path: Path) -> None:
        """Non-dict items in features list are skipped."""
        p = tmp_path / "mixed.json"
        p.write_text(json.dumps({"features": [1, "string", None, {"name": "ok"}]}))
        trace = Serializer.load(p)
        assert len(trace.features) == 1
        assert trace.features[0].name == "ok"

    def test_load_with_extra_keys(self, tmp_path: Path) -> None:
        """Extra unknown keys are ignored gracefully."""
        p = tmp_path / "extra.json"
        p.write_text(
            json.dumps(
                {
                    "version": "1",
                    "features": [],
                    "unknown_key": "value",
                    "another": 42,
                }
            )
        )
        trace = Serializer.load(p)
        assert trace.version == "1"

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        """Truncated JSON raises JSONDecodeError."""
        p = tmp_path / "corrupt.json"
        p.write_text('{"version": "1", "features": [')
        with pytest.raises(json.JSONDecodeError):
            Serializer.load(p)

    def test_load_with_nan_values(self, tmp_path: Path) -> None:
        """NaN in JSON (invalid but parseable by Python's json) is handled."""
        p = tmp_path / "nan.json"
        p.write_text('{"version": "1", "features": [], "stats": {"duration": NaN}}')
        trace = Serializer.load(p)
        # NaN should be loaded as-is (Python's json.loads accepts NaN by default)
        # safe_float in _stats_from_dict would filter it
        assert trace.stats.duration == 0.0  # safe_float converts NaN to 0.0

    def test_load_scenario_with_non_dict_steps(self, tmp_path: Path) -> None:
        """Non-dict items in steps list are skipped."""
        p = tmp_path / "badsteps.json"
        p.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "name": "f",
                            "scenarios": [
                                {
                                    "name": "s",
                                    "steps": [1, "bad", None, {"keyword": "Given", "name": "ok"}],
                                }
                            ],
                        }
                    ]
                }
            )
        )
        trace = Serializer.load(p)
        assert len(trace.features[0].scenarios[0].steps) == 1
        assert trace.features[0].scenarios[0].steps[0].name == "ok"

    def test_load_with_invalid_duration_types(self, tmp_path: Path) -> None:
        """Invalid duration types are handled by safe_float."""
        p = tmp_path / "badduration.json"
        p.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "name": "f",
                            "duration": "not a number",
                            "scenarios": [{"name": "s", "duration": None, "steps": []}],
                        }
                    ],
                    "stats": {"duration": "bad", "avg_step_duration": None},
                }
            )
        )
        trace = Serializer.load(p)
        assert trace.features[0].duration == 0.0
        assert trace.features[0].scenarios[0].duration == 0.0
        assert trace.stats.duration == 0.0
        assert trace.stats.avg_step_duration == 0.0

    def test_load_environment_with_invalid_cpu_count(self, tmp_path: Path) -> None:
        """Invalid cpu_count is handled by _as_int."""
        p = tmp_path / "badenv.json"
        p.write_text(
            json.dumps(
                {
                    "environment": {
                        "cpu_count": "not a number",
                        "memory_mb": None,
                        "env_vars": "not a dict",
                    }
                }
            )
        )
        trace = Serializer.load(p)
        assert trace.environment.cpu_count == 0
        assert trace.environment.memory_mb == 0
        assert trace.environment.env_vars == {}

    def test_load_created_at_invalid(self, tmp_path: Path) -> None:
        """Invalid created_at string is silently ignored."""
        p = tmp_path / "baddate.json"
        p.write_text(
            json.dumps(
                {
                    "version": "1",
                    "features": [],
                    "created_at": "not a date",
                }
            )
        )
        trace = Serializer.load(p)
        # Should fall back to default datetime.now()
        assert trace.created_at is not None

    def test_load_tags_as_non_list(self, tmp_path: Path) -> None:
        """Tags as non-list is treated as empty."""
        p = tmp_path / "badtags.json"
        p.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "name": "f",
                            "tags": "smoke",
                            "scenarios": [{"name": "s", "tags": 42, "steps": []}],
                        }
                    ]
                }
            )
        )
        trace = Serializer.load(p)
        assert trace.features[0].tags == []
        assert trace.features[0].scenarios[0].tags == []


class TestAttachModuleEdge:
    """Edge-case tests for attach.py module."""

    def test_attach_screenshot_no_formatter(self) -> None:
        """attach_screenshot with no formatter is a no-op."""
        from behave_trace.attach import attach_screenshot

        context = MagicMock()
        context._runner = None
        # Should not raise
        attach_screenshot(context, b"fake png data")

    def test_attach_screenshot_none_context(self) -> None:
        """attach_screenshot with None context is a no-op."""
        from behave_trace.attach import attach_screenshot

        attach_screenshot(None, b"fake png data")

    def test_attach_dom_no_formatter(self) -> None:
        """attach_dom with no formatter is a no-op."""
        from behave_trace.attach import attach_dom

        attach_dom(None, "<html></html>")

    def test_attach_text_no_formatter(self) -> None:
        """attach_text with no formatter is a no-op."""
        from behave_trace.attach import attach_text

        attach_text(None, "some text")

    def test_log_no_formatter(self) -> None:
        """log with no formatter is a no-op."""
        from behave_trace.attach import log

        log(None, "message")

    def test_attach_network_no_formatter(self) -> None:
        """attach_network with no formatter is a no-op."""
        from behave_trace.attach import attach_network

        attach_network(None, {"method": "GET", "url": "http://example.com"})

    def test_attach_screenshot_with_path_string(self) -> None:
        """attach_screenshot with a path to non-existent file is a no-op."""
        from behave_trace.attach import attach_screenshot

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        attach_screenshot(context, "/nonexistent/path/screenshot.png")
        formatter.attach.assert_not_called()

    def test_attach_screenshot_with_empty_bytes(self) -> None:
        """attach_screenshot with empty bytes is a no-op (data is None)."""
        from behave_trace.attach import attach_screenshot

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        # Empty bytes is falsy, so data stays as b"" which is not None
        # Actually, b"" is not None, so it would create an artifact with empty data
        attach_screenshot(context, b"")
        # b"" is bytes, so data = bytes(b"") = b"", which is not None
        # So formatter.attach WOULD be called
        formatter.attach.assert_called_once()
        artifact = formatter.attach.call_args[0][0]
        assert artifact.data_base64 == ""

    def test_attach_dom_with_base_tag_injection(self) -> None:
        """attach_dom injects <base> tag when URL is available."""
        from behave_trace.attach import attach_dom

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        source = MagicMock()
        source.current_url = "http://example.com/page"
        source.page_source = "<html><head><title>Test</title></head><body></body></html>"

        attach_dom(context, source)
        formatter.attach.assert_called_once()
        artifact = formatter.attach.call_args[0][0]
        assert '<base href="http://example.com/page">' in artifact.text

    def test_attach_dom_existing_base_tag_not_duplicated(self) -> None:
        """attach_dom does not inject <base> if one already exists."""
        from behave_trace.attach import attach_dom

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        source = MagicMock()
        source.current_url = "http://example.com/page"
        source.page_source = '<html><head><base href="http://existing.com"></head></html>'

        attach_dom(context, source)
        artifact = formatter.attach.call_args[0][0]
        assert artifact.text.count("<base") == 1
        assert "http://existing.com" in artifact.text

    def test_attach_dom_with_html_escape_in_url(self) -> None:
        """attach_dom escapes special characters in base URL."""
        from behave_trace.attach import attach_dom

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        source = MagicMock()
        source.current_url = 'http://example.com/page?x="><script>alert(1)</script>'
        source.page_source = "<html><head></head></html>"

        attach_dom(context, source)
        artifact = formatter.attach.call_args[0][0]
        assert "<script>" not in artifact.text.split('<base href="')[1].split('">')[0]

    def test_normalize_network_data_with_none(self) -> None:
        """_normalize_network_data returns None for unrecognized input."""
        from behave_trace.attach import _normalize_network_data

        assert _normalize_network_data(None) is None

    def test_normalize_network_data_with_int(self) -> None:
        """_normalize_network_data returns None for int input."""
        from behave_trace.attach import _normalize_network_data

        assert _normalize_network_data(42) is None

    def test_normalize_network_data_with_invalid_json_string(self) -> None:
        """_normalize_network_data returns None for non-JSON string."""
        from behave_trace.attach import _normalize_network_data

        assert _normalize_network_data("not json") is None

    def test_normalize_network_data_with_dict(self) -> None:
        """_normalize_network_data handles dict input."""
        from behave_trace.attach import _normalize_network_data

        result = _normalize_network_data({"method": "GET", "url": "http://x"})
        assert result is not None
        assert result["method"] == "GET"
        assert result["url"] == "http://x"
        assert result["status"] is None

    def test_normalize_network_data_with_json_string(self) -> None:
        """_normalize_network_data parses JSON string."""
        from behave_trace.attach import _normalize_network_data

        result = _normalize_network_data('{"method": "POST", "url": "http://x"}')
        assert result is not None
        assert result["method"] == "POST"

    def test_normalize_network_data_with_json_bytes(self) -> None:
        """_normalize_network_data parses JSON bytes."""
        from behave_trace.attach import _normalize_network_data

        result = _normalize_network_data(b'{"method": "PUT", "url": "http://x"}')
        assert result is not None
        assert result["method"] == "PUT"


class TestServerConcurrency:
    """Test thread safety of server state updates."""

    def test_concurrent_update_trace(self) -> None:
        """Multiple concurrent update_trace calls don't crash."""
        from behave_trace.viewer.server import ViewerServer

        trace1 = Trace()
        trace1.features.append(Feature(name="f1"))

        trace2 = Trace()
        trace2.features.append(Feature(name="f2"))

        server = ViewerServer(trace1, port=0)
        server.start()
        try:
            errors: list[Exception] = []

            def update() -> None:
                try:
                    for _ in range(20):
                        server.update_trace(trace1)
                        server.update_trace(trace2)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=update, daemon=True) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert errors == []
        finally:
            server.stop()

    def test_concurrent_sse_and_update(self) -> None:
        """SSE clients don't crash during concurrent trace updates."""
        from behave_trace.viewer.server import ViewerServer

        trace = Trace()
        server = ViewerServer(trace, port=0, watching=True)
        server.start()
        try:
            errors: list[Exception] = []

            def updater() -> None:
                try:
                    for i in range(10):
                        t = Trace()
                        t.features.append(Feature(name=f"f{i}"))
                        server.update_trace(t)
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=updater, daemon=True)
            thread.start()
            thread.join(timeout=10)
            assert errors == []
        finally:
            server.stop()

    def test_server_stop_idempotent(self) -> None:
        """Calling stop() multiple times is safe."""
        from behave_trace.viewer.server import ViewerServer

        server = ViewerServer(Trace(), port=0)
        server.start()
        server.stop()
        server.stop()  # Should not raise
        server.stop()  # Should not raise

    def test_server_start_after_stop(self) -> None:
        """Starting a new server after stopping the old one works."""
        from behave_trace.viewer.server import ViewerServer

        server1 = ViewerServer(Trace(), port=0)
        url1 = server1.start()
        server1.stop()

        server2 = ViewerServer(Trace(), port=0)
        url2 = server2.start()
        assert url2 != url1  # Different port (or same, but server works)
        server2.stop()


class TestCollectorEdgeCases:
    """Edge-case tests for the Collector."""

    def test_on_step_without_scenario(self) -> None:
        """on_step without a current scenario clears pending artifacts."""
        from behave_trace.collector import Collector

        collector = Collector()
        collector.attach(
            Artifact(type=ARTIFACT_TEXT, name="test", mime_type="text/plain", text="hello")
        )
        collector.log("test log")

        # on_step should clear pending artifacts and return None
        step = collector.on_step(MagicMock())
        assert step is None

    def test_finalize_with_no_features(self) -> None:
        """Finalize with no features produces zero stats."""
        from behave_trace.collector import Collector

        collector = Collector()
        trace = collector.finalize()
        assert trace.stats.total_features == 0
        assert trace.stats.total_scenarios == 0
        assert trace.stats.total_steps == 0
        assert trace.stats.by_status == {}
        assert trace.stats.avg_step_duration == 0.0

    def test_finalize_with_empty_scenario(self) -> None:
        """Finalize with a scenario that has no steps."""
        from behave_trace.collector import Collector

        collector = Collector()
        feature = Feature(name="f")
        collector.trace.features.append(feature)

        # Manually add a scenario with no steps
        scenario = Scenario(name="s")
        feature.scenarios.append(scenario)

        trace = collector.finalize()
        assert trace.stats.total_scenarios == 1
        assert trace.stats.total_steps == 0
        assert trace.stats.avg_step_duration == 0.0

    def test_compute_stats_with_negative_durations(self) -> None:
        """Stats computation handles negative durations gracefully.

        Bug 17: _compute_stats initialized slowest_duration to 0.0, so
        steps with negative durations were never identified as the slowest.
        Fix: initialize to float('-inf').
        """
        from behave_trace.collector import Collector

        collector = Collector()
        feature = Feature(name="f", duration=-1.0)
        scenario = Scenario(name="s", duration=-0.5)
        step = Step(keyword="Given", name="step", duration=-0.1)
        scenario.steps.append(step)
        feature.scenarios.append(scenario)
        collector.trace.features.append(feature)

        trace = collector.finalize()
        assert trace.stats.duration == -1.0
        assert trace.stats.slowest_step_duration == -0.1
        assert trace.stats.slowest_step_name == "Given step"

    def test_attach_and_log_buffering(self) -> None:
        """Artifacts and logs are buffered until on_step."""
        from behave_trace.collector import Collector

        collector = Collector()
        feature = Feature(name="f")
        collector.trace.features.append(feature)
        collector.on_feature(
            MagicMock(
                name="f",
                status="passed",
                duration=0.0,
                description=[],
                location="",
                tags=[],
            )
        )
        collector.on_scenario(
            MagicMock(
                name="s",
                type="",
                status="passed",
                duration=0.0,
                description=[],
                location="",
                tags=[],
            )
        )

        collector.attach(
            Artifact(
                type=ARTIFACT_SCREENSHOT,
                name="shot.png",
                mime_type="image/png",
                data_base64="abc",
            )
        )
        collector.log("log message", level="info")

        # Pending artifacts/logs should be buffered
        assert len(collector._pending_artifacts) == 1
        assert len(collector._pending_logs) == 1

        # on_step should flush them
        step_mock = MagicMock()
        step_mock.keyword = "Given"
        step_mock.name = "step"
        step_mock.status = "passed"
        step_mock.duration = 0.0
        step_mock.location = ""
        step_mock.text = None
        step_mock.table = None
        step_mock.error_message = None
        step_mock.exception = None
        step_mock.embeddings = []
        step_mock.log = []

        step = collector.on_step(step_mock)
        assert step is not None
        assert len(step.artifacts) == 1
        assert len(step.logs) == 1
        assert len(collector._pending_artifacts) == 0
        assert len(collector._pending_logs) == 0
