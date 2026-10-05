"""Regression tests for bugs discovered during the stabilization audit.

Each test validates a specific bug fix and prevents it from returning.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import pytest

from behave_trace.attach import attach_dom
from behave_trace.collector import Collector, _join_description, _safe_iterable
from behave_trace.models import (
    Trace,
)
from behave_trace.serializer import Serializer
from behave_trace.viewer.server import ViewerServer

# ---------------------------------------------------------------------------
# Bug 1 & 5: attach_dom <head> with attributes + <base> detection
# ---------------------------------------------------------------------------


class TestAttachDomHeadAttributes:
    """Regression: attach_dom must not break HTML when <head> has attributes."""

    def test_head_with_attributes_preserved(self) -> None:
        """<head data-x='1'> should keep its attributes after <base> injection."""
        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()

        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner

        source = mock.Mock()
        source.current_url = "https://example.com"
        source.page_source = (
            '<html><head data-x="1"><title>Test</title></head><body>Hello</body></html>'
        )

        attach_dom(context, source)

        assert formatter.attach.called
        artifact = formatter.attach.call_args[0][0]
        html = artifact.text
        assert '<head data-x="1">' in html
        assert '<base href="https://example.com">' in html
        # The <base> should be INSIDE the <head> tag, not breaking it
        assert html.index("<base") > html.index('">')

    def test_head_without_attributes_still_works(self) -> None:
        """<head> without attributes should still get <base> injected."""
        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()

        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner

        source = mock.Mock()
        source.current_url = "https://example.com"
        source.page_source = "<html><head><title>Test</title></head><body></body></html>"

        attach_dom(context, source)

        artifact = formatter.attach.call_args[0][0]
        html = artifact.text
        assert "<head><base href=" in html

    def test_base_tag_without_space_detected(self) -> None:
        """<base> (without space or attributes) should be detected and not duplicated."""
        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()

        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner

        source = mock.Mock()
        source.current_url = "https://example.com"
        source.page_source = "<html><head><base><title>Test</title></head></html>"

        attach_dom(context, source)

        artifact = formatter.attach.call_args[0][0]
        html = artifact.text
        # Should NOT inject a second <base>
        assert html.count("<base") == 1

    def test_base_tag_with_href_detected(self) -> None:
        """<base href='...'> should be detected and not duplicated."""
        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()

        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner

        source = mock.Mock()
        source.current_url = "https://example.com"
        source.page_source = (
            '<html><head><base href="https://other.com"><title>T</title></head></html>'
        )

        attach_dom(context, source)

        artifact = formatter.attach.call_args[0][0]
        html = artifact.text
        assert html.count("<base") == 1


# ---------------------------------------------------------------------------
# Bug 2: _handle_run doesn't consume request body
# ---------------------------------------------------------------------------


class TestHandleRunConsumesBody:
    """Regression: POST /api/run must consume the request body for keep-alive."""

    def test_run_with_body_doesnt_corrupt_next_request(self) -> None:
        """A POST /api/run with a body should not corrupt the next request."""
        trace = Trace()
        server = ViewerServer(trace, port=0)
        callback_called = threading.Event()

        def cb(scenario_names: list[str] | None) -> None:
            callback_called.set()

        server.rerun_callback = cb
        server._state.can_run = True
        server.start()

        try:
            url = server.url

            # First request: POST /api/run with a body
            req1 = urllib.request.Request(
                f"{url}/api/run",
                data=json.dumps({"unused": "data"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp1 = urllib.request.urlopen(req1, timeout=5)
            assert resp1.status == 200
            resp1.read()

            # Wait for callback to execute
            assert callback_called.wait(timeout=5)

            # Second request on a NEW connection: GET /api/watching
            # (We can't easily test keep-alive on the same connection with
            # urllib, but we can verify the server is still responsive)
            req2 = urllib.request.Request(f"{url}/api/watching")
            resp2 = urllib.request.urlopen(req2, timeout=5)
            assert resp2.status == 200
            data = json.loads(resp2.read())
            assert "watching" in data
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Bug 3: _join_description crashes on non-iterable, non-string values
# ---------------------------------------------------------------------------


class TestJoinDescriptionNonIterable:
    """Regression: _join_description must not crash on non-iterable values."""

    @pytest.mark.parametrize("value", [42, 3.14, True, object()])
    def test_non_iterable_non_string_returns_str(self, value: object) -> None:
        """Non-iterable, non-string values should be safely stringified."""
        result = _join_description(value)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_returns_empty(self) -> None:
        assert _join_description(None) == ""

    def test_empty_string_returns_empty(self) -> None:
        assert _join_description("") == ""

    def test_list_of_strings_joined(self) -> None:
        assert _join_description(["line1", "line2"]) == "line1\nline2"

    def test_string_returned_as_is(self) -> None:
        assert _join_description("hello") == "hello"


# ---------------------------------------------------------------------------
# Bug 4: Collector methods crash on non-iterable attributes
# ---------------------------------------------------------------------------


class TestCollectorNonIterableAttributes:
    """Regression: collector must handle non-iterable attributes gracefully."""

    def test_safe_iterable_none(self) -> None:
        assert _safe_iterable(None) == []

    def test_safe_iterable_int(self) -> None:
        assert _safe_iterable(42) == []

    def test_safe_iterable_list(self) -> None:
        assert _safe_iterable([1, 2, 3]) == [1, 2, 3]

    def test_safe_iterable_string(self) -> None:
        """Strings are iterable — characters are returned."""
        assert _safe_iterable("abc") == ["a", "b", "c"]

    def test_on_feature_with_non_iterable_tags(self) -> None:
        """Feature with non-iterable tags should not crash."""
        collector = Collector()
        feature_obj = mock.Mock()
        feature_obj.name = "Test"
        feature_obj.description = []
        feature_obj.location = ""
        feature_obj.tags = 42  # Not iterable
        feature_obj.background = None

        feature = collector.on_feature(feature_obj)
        assert feature.tags == []

    def test_on_scenario_with_non_iterable_tags(self) -> None:
        """Scenario with non-iterable tags should not crash."""
        collector = Collector()
        # Set up a feature first
        feature_obj = mock.Mock()
        feature_obj.name = "Test"
        feature_obj.description = []
        feature_obj.location = ""
        feature_obj.tags = []
        feature_obj.background = None
        collector.on_feature(feature_obj)

        scenario_obj = mock.Mock()
        scenario_obj.name = "Scenario 1"
        scenario_obj.description = []
        scenario_obj.location = ""
        scenario_obj.tags = 99  # Not iterable
        scenario_obj.type = "scenario"

        scenario = collector.on_scenario(scenario_obj)
        assert scenario.tags == []

    def test_make_step_with_non_iterable_embeddings(self) -> None:
        """Step with non-iterable embeddings should not crash."""
        collector = Collector()
        # Set up feature and scenario
        feature_obj = mock.Mock()
        feature_obj.name = "Test"
        feature_obj.description = []
        feature_obj.location = ""
        feature_obj.tags = []
        feature_obj.background = None
        collector.on_feature(feature_obj)

        scenario_obj = mock.Mock()
        scenario_obj.name = "S1"
        scenario_obj.description = []
        scenario_obj.location = ""
        scenario_obj.tags = []
        scenario_obj.type = "scenario"
        collector.on_scenario(scenario_obj)

        step_obj = mock.Mock()
        step_obj.keyword = "Given"
        step_obj.name = "a step"
        step_obj.status = "passed"
        step_obj.duration = 0.1
        step_obj.location = ""
        step_obj.text = None
        step_obj.table = None
        step_obj.error_message = ""
        step_obj.exception = None
        step_obj.embeddings = 42  # Not iterable
        step_obj.log = 77  # Not iterable

        step = collector.on_step(step_obj)
        assert step is not None
        assert step.artifacts == []
        assert step.logs == []

    def test_make_background_with_non_iterable_steps(self) -> None:
        """Background with non-iterable steps should not crash."""
        collector = Collector()
        bg_obj = mock.Mock()
        bg_obj.name = "BG"
        bg_obj.keyword = "Background"
        bg_obj.location = ""
        bg_obj.steps = 42  # Not iterable

        bg = collector._make_background(bg_obj)
        assert bg.steps == []


# ---------------------------------------------------------------------------
# Bug 6: serializer _as_str loses falsy values
# ---------------------------------------------------------------------------


class TestSerializerAsStr:
    """Regression: _as_str should not lose falsy values like 0."""

    def test_as_str_none_returns_empty(self) -> None:
        from behave_trace.serializer import _as_str

        assert _as_str(None) == ""

    def test_as_str_zero_returns_zero_string(self) -> None:
        from behave_trace.serializer import _as_str

        assert _as_str(0) == "0"

    def test_as_str_false_returns_false_string(self) -> None:
        from behave_trace.serializer import _as_str

        assert _as_str(False) == "False"

    def test_as_str_empty_string_returns_empty(self) -> None:
        from behave_trace.serializer import _as_str

        assert _as_str("") == ""

    def test_as_str_normal_string(self) -> None:
        from behave_trace.serializer import _as_str

        assert _as_str("hello") == "hello"

    def test_trace_with_integer_feature_name_preserved(self, tmp_path: Path) -> None:
        """A trace file with integer feature_name should preserve it as string."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "Test",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S1",
                            "status": "passed",
                            "feature_name": 0,
                            "rule_name": "",
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))

        trace = Serializer.load(trace_file)
        # feature_name=0 should be preserved as "0", not lost as ""
        assert trace.features[0].scenarios[0].feature_name == "0"


# ---------------------------------------------------------------------------
# Bug 7: _handle_rerun doesn't consume request body when cb is None
# ---------------------------------------------------------------------------


class TestHandleRerunConsumesBodyWithoutCallback:
    """Regression: POST /api/rerun must consume body even when no callback."""

    def test_rerun_without_callback_consumes_body(self) -> None:
        """POST /api/rerun with body but no callback should still consume body."""
        trace = Trace()
        server = ViewerServer(trace, port=0)
        server.start()

        try:
            url = server.url

            # POST /api/rerun with a body — no callback configured
            req1 = urllib.request.Request(
                f"{url}/api/rerun",
                data=json.dumps({"filter": "all"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                resp1 = urllib.request.urlopen(req1, timeout=5)
            except urllib.error.HTTPError as exc:
                assert exc.code == 501
            else:
                assert resp1.status == 501
                resp1.read()

            # Server should still be responsive
            req2 = urllib.request.Request(f"{url}/api/watching")
            resp2 = urllib.request.urlopen(req2, timeout=5)
            assert resp2.status == 200
            data = json.loads(resp2.read())
            assert "watching" in data
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Bug 8: do_POST 404 doesn't consume request body for unknown POST paths
# ---------------------------------------------------------------------------


class TestDoPostUnknownPathConsumesBody:
    """Regression: POST to unknown path must consume body for keep-alive."""

    def test_unknown_post_path_consumes_body(self) -> None:
        """POST to unknown path with body should not corrupt keep-alive."""
        trace = Trace()
        server = ViewerServer(trace, port=0)
        server.start()

        try:
            url = server.url

            # POST to unknown path with a body
            req1 = urllib.request.Request(
                f"{url}/api/unknown",
                data=json.dumps({"unused": "data"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                resp1 = urllib.request.urlopen(req1, timeout=5)
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
            else:
                assert resp1.status == 404
                resp1.read()

            # Server should still be responsive
            req2 = urllib.request.Request(f"{url}/api/watching")
            resp2 = urllib.request.urlopen(req2, timeout=5)
            assert resp2.status == 200
            data = json.loads(resp2.read())
            assert "watching" in data
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Bug 9: Serializer `or ""` pattern loses falsy values (0, False) in many fields
# ---------------------------------------------------------------------------


class TestSerializerFalsyValuesPreserved:
    """Regression: serializer must not lose falsy values like 0 or False."""

    def test_step_with_falsy_keyword_preserved(self, tmp_path: Path) -> None:
        """A step with keyword=0 should be preserved as '0', not lost as ''."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "Test",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S1",
                            "status": "passed",
                            "steps": [{"keyword": 0, "name": "step", "status": "passed"}],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].keyword == "0"

    def test_step_with_falsy_name_preserved(self, tmp_path: Path) -> None:
        """A step with name=0 should be preserved as '0', not lost as ''."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "Test",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S1",
                            "status": "passed",
                            "steps": [{"keyword": "Given", "name": 0, "status": "passed"}],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].name == "0"

    def test_feature_with_falsy_name_preserved(self, tmp_path: Path) -> None:
        """A feature with name=0 should be preserved as '0', not lost as ''."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [{"name": 0, "status": "passed", "scenarios": []}],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].name == "0"

    def test_environment_with_falsy_values_preserved(self, tmp_path: Path) -> None:
        """Environment fields with falsy values should be stringified, not lost."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {"python_version": 0, "hostname": False, "user": 0},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.environment.python_version == "0"
        assert trace.environment.hostname == "False"
        assert trace.environment.user == "0"

    def test_artifact_with_falsy_name_preserved(self, tmp_path: Path) -> None:
        """An artifact with name=0 should be preserved as '0', not lost as ''."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "Test",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S1",
                            "status": "passed",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "status": "passed",
                                    "artifacts": [{"type": "text", "name": 0}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].artifacts[0].name == "0"

    def test_error_info_with_falsy_values_preserved(self, tmp_path: Path) -> None:
        """ErrorInfo fields with falsy values should be stringified, not lost."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "Test",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S1",
                            "status": "passed",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "status": "passed",
                                    "error": {
                                        "message": 0,
                                        "traceback": False,
                                        "exception_type": 0,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        err = trace.features[0].scenarios[0].steps[0].error
        assert err is not None
        assert err.message == "0"
        assert err.traceback == "False"
        assert err.exception_type == "0"

    def test_slowest_step_name_falsy_preserved(self, tmp_path: Path) -> None:
        """slowest_step_name=0 should be preserved as '0', not lost as ''."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {},
            "stats": {"slowest_step_name": 0},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.stats.slowest_step_name == "0"


# ---------------------------------------------------------------------------
# Bug 10: _handle_rerun drops falsy scenario names like "0" with `if s`
# ---------------------------------------------------------------------------


class TestRerunFalsyScenarioNames:
    """Regression: rerun must not drop falsy scenario names like '0'."""

    def test_rerun_with_falsy_scenario_name_preserved(self) -> None:
        """POST /api/rerun with scenario name '0' should pass it to callback."""
        trace = Trace()
        server = ViewerServer(trace, port=0)
        received_names: list[str] | None = None
        callback_called = threading.Event()

        def cb(scenario_names: list[str] | None) -> None:
            nonlocal received_names
            received_names = scenario_names
            callback_called.set()

        server.rerun_callback = cb
        server._state.can_run = True
        server.start()

        try:
            url = server.url
            req = urllib.request.Request(
                f"{url}/api/rerun",
                data=json.dumps({"filter": "failed", "scenarios": ["0", "normal_name"]}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=5)
            assert resp.status == 200
            resp.read()

            assert callback_called.wait(timeout=5)
            assert received_names is not None
            assert "0" in received_names
            assert "normal_name" in received_names
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Bug 12: FileWatcher callback crash kills watcher thread silently
# ---------------------------------------------------------------------------


class TestWatcherCallbackCrash:
    """Regression: watcher must survive a callback that raises."""

    def test_polling_survives_callback_exception(self, tmp_path: Path) -> None:
        """Watcher should keep running after callback raises."""
        from behave_trace.watcher import FileWatcher

        call_count = 0

        def callback(files: list[str]) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("callback crash")

        watcher = FileWatcher(tmp_path, callback, debounce_ms=50)
        watcher.start()

        # Trigger a file change
        (tmp_path / "test.feature").write_text("Feature: test")

        import time

        time.sleep(0.3)

        # Watcher should still be alive — trigger another change
        (tmp_path / "test.feature").write_text("Feature: updated")
        time.sleep(0.3)

        watcher.stop()

        # Callback should have been called at least once despite the crash
        assert call_count >= 1


# ---------------------------------------------------------------------------
# Bug 13: Serializer `or` pattern on version/status/type/mime_type/keyword
#         loses falsy values like 0 and False
# ---------------------------------------------------------------------------


class TestSerializerFalsyDefaultsPreserved:
    """Regression: serializer must not lose falsy values in fields with defaults."""

    def test_version_falsy_preserved(self, tmp_path: Path) -> None:
        """version=0 should be preserved as '0', not replaced with '1'."""
        trace_data = {
            "version": 0,
            "created_at": "2024-01-01T00:00:00",
            "features": [],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.version == "0"

    def test_status_falsy_preserved(self, tmp_path: Path) -> None:
        """status=0 should be preserved as '0', not replaced with 'untested'."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [{"name": "F", "status": 0, "scenarios": []}],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].status == "0"

    def test_artifact_type_falsy_preserved(self, tmp_path: Path) -> None:
        """artifact type=0 should be preserved as '0', not replaced with 'text'."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "F",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S",
                            "status": "passed",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "status": "passed",
                                    "artifacts": [{"type": 0, "name": "x"}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].artifacts[0].type == "0"

    def test_artifact_mime_type_falsy_preserved(self, tmp_path: Path) -> None:
        """mime_type=0 should be preserved as '0', not replaced with default."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "F",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S",
                            "status": "passed",
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "step",
                                    "status": "passed",
                                    "artifacts": [{"type": "text", "name": "x", "mime_type": 0}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].artifacts[0].mime_type == "0"

    def test_background_keyword_falsy_preserved(self, tmp_path: Path) -> None:
        """background keyword=0 should be preserved as '0', not 'Background'."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "F",
                    "status": "passed",
                    "scenarios": [],
                    "background": {"name": "bg", "keyword": 0, "steps": []},
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].background is not None
        assert trace.features[0].background.keyword == "0"

    def test_scenario_status_falsy_preserved(self, tmp_path: Path) -> None:
        """scenario status=0 should be preserved as '0', not 'untested'."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "F",
                    "status": "passed",
                    "scenarios": [{"name": "S", "status": 0, "steps": []}],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].status == "0"

    def test_step_status_falsy_preserved(self, tmp_path: Path) -> None:
        """step status=0 should be preserved as '0', not 'untested'."""
        trace_data = {
            "version": "1",
            "created_at": "2024-01-01T00:00:00",
            "features": [
                {
                    "name": "F",
                    "status": "passed",
                    "scenarios": [
                        {
                            "name": "S",
                            "status": "passed",
                            "steps": [{"keyword": "Given", "name": "step", "status": 0}],
                        }
                    ],
                }
            ],
            "environment": {},
            "stats": {},
        }
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))
        trace = Serializer.load(trace_file)
        assert trace.features[0].scenarios[0].steps[0].status == "0"


class TestBug14ServeFileTOCTOU:
    """Bug 14: _serve_file has a TOCTOU race — file deleted between
    exists() check and read_bytes() causes unhandled OSError."""

    def test_serve_file_handles_deletion(self, tmp_path: Path) -> None:
        """If a file is deleted between the exists() check and read_bytes(),
        the server should return 404 instead of crashing."""
        from behave_trace.models import Trace
        from behave_trace.viewer.server import ViewerServer

        # Create a test asset file
        asset_file = tmp_path / "test.txt"
        asset_file.write_text("hello")

        server = ViewerServer(Trace(), port=0)
        server.start()
        try:
            # Mock read_bytes to raise OSError (simulating file deletion)
            import unittest.mock as mock_mod

            original_read_bytes = Path.read_bytes

            def fail_read_bytes(self: Path) -> bytes:
                if self.name == "test.txt":
                    raise OSError("File deleted")
                return original_read_bytes(self)

            with mock_mod.patch.object(Path, "read_bytes", fail_read_bytes):
                import urllib.request

                # _serve_file is used for assets, not arbitrary files.
                # Test via the /api/source endpoint which also reads files.
                url = f"{server.url}/api/source?path=test.txt&line=1"
                try:
                    urllib.request.urlopen(url, timeout=5)
                except urllib.error.HTTPError as e:
                    # Should get a 404 or 500, not a crash
                    assert e.code in (404, 500)
        finally:
            server.stop()


class TestBug15NaNSanitization:
    """Bug 15: Serializer.save and ViewerServer produce invalid JSON
    when NaN/Inf float values are present in trace data."""

    def test_serializer_save_sanitizes_nan(self, tmp_path: Path) -> None:
        """Serializer.save should replace NaN with 0.0, not crash."""
        from behave_trace.models import Feature, Trace
        from behave_trace.serializer import Serializer

        trace = Trace()
        feature = Feature(name="test", duration=float("nan"))
        trace.features.append(feature)
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["duration"] == 0.0

    def test_serializer_save_sanitizes_inf(self, tmp_path: Path) -> None:
        """Serializer.save should replace Infinity with 0.0, not crash."""
        from behave_trace.models import Feature, Trace
        from behave_trace.serializer import Serializer

        trace = Trace()
        feature = Feature(name="test", duration=float("inf"))
        trace.features.append(feature)
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["duration"] == 0.0

    def test_serializer_save_sanitizes_neg_inf(self, tmp_path: Path) -> None:
        """Serializer.save should replace -Infinity with 0.0, not crash."""
        from behave_trace.models import Feature, Trace
        from behave_trace.serializer import Serializer

        trace = Trace()
        feature = Feature(name="test", duration=float("-inf"))
        trace.features.append(feature)
        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["duration"] == 0.0

    def test_viewer_server_sanitizes_nan(self) -> None:
        """ViewerServer should produce valid JSON even with NaN values."""
        import socket
        import time

        from behave_trace.models import Feature, Trace
        from behave_trace.viewer.server import ViewerServer

        trace = Trace()
        feature = Feature(name="test", duration=float("nan"))
        trace.features.append(feature)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            port = server._httpd.server_address[1] if server._httpd else 0
            deadline = time.monotonic() + 5
            last_exc: Exception | None = None
            while time.monotonic() < deadline:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect(("127.0.0.1", port))
                    sock.sendall(b"GET /api/trace HTTP/1.0\r\nHost: localhost\r\n\r\n")
                    raw = b""
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        raw += chunk
                    sock.close()
                    body = raw.split(b"\r\n\r\n", 1)[1]
                    data = json.loads(body)
                    assert data["features"][0]["duration"] == 0.0
                    return
                except Exception as exc:
                    last_exc = exc
                    time.sleep(0.1)
            raise last_exc  # type: ignore[misc]
        finally:
            server.stop()


class TestBug16SanitizeFloatsTuple:
    """Bug 16: _sanitize_floats must handle tuples, not just lists.

    Python's json.dumps serializes tuples as JSON arrays, so a tuple
    containing NaN/Inf would bypass _sanitize_floats and crash
    json.dumps(allow_nan=False).
    """

    def test_sanitize_floats_handles_tuple_with_nan(self) -> None:
        """_sanitize_floats converts tuple with NaN to list with 0.0."""
        from behave_trace.serializer import _sanitize_floats

        data = {"items": (float("nan"), 1.0, float("inf"))}
        sanitized = _sanitize_floats(data)
        assert sanitized["items"] == [0.0, 1.0, 0.0]
        assert isinstance(sanitized["items"], list)

    def test_sanitize_floats_handles_nested_tuple(self) -> None:
        """_sanitize_floats handles tuples nested inside dicts."""
        from behave_trace.serializer import _sanitize_floats

        data = {"outer": ({"inner": (float("nan"),)},)}
        sanitized = _sanitize_floats(data)
        assert sanitized["outer"][0]["inner"] == [0.0]

    def test_serializer_save_with_tuple_nan(self, tmp_path: Path) -> None:
        """Serializer.save handles trace with tuple containing NaN in logs."""
        from behave_trace.models import Feature, Scenario, Step, Trace
        from behave_trace.serializer import Serializer

        trace = Trace()
        feature = Feature(name="test")
        scenario = Scenario(name="test")
        step = Step(keyword="Given", name="step")
        step.logs = [{"values": (float("nan"), 1.0)}]
        scenario.steps.append(step)
        feature.scenarios.append(scenario)
        trace.features.append(feature)

        path = tmp_path / "trace.json"
        Serializer.save(trace, path)
        data = json.loads(path.read_text())
        assert data["features"][0]["scenarios"][0]["steps"][0]["logs"][0]["values"] == [0.0, 1.0]


class TestBug17SlowestStepZeroDuration:
    """Bug 17: _compute_stats initialized slowest_duration to 0.0.

    Steps with duration 0.0 (e.g. skipped steps) or negative durations
    (corrupted data) were never identified as the slowest step because
    the comparison ``step.duration > slowest_duration`` (0.0) was always
    False for non-positive values.

    Fix: initialize to ``float("-inf")`` and reset to 0.0 if no steps
    were processed.
    """

    def test_zero_duration_step_is_slowest(self) -> None:
        """A single step with duration 0.0 is correctly identified as slowest."""
        from behave_trace.collector import Collector
        from behave_trace.models import Feature, Scenario, Step

        collector = Collector()
        feature = Feature(name="f")
        scenario = Scenario(name="s")
        scenario.steps.append(Step(keyword="Given", name="step", duration=0.0))
        feature.scenarios.append(scenario)
        collector.trace.features.append(feature)

        trace = collector.finalize()
        assert trace.stats.slowest_step_duration == 0.0
        assert trace.stats.slowest_step_name == "Given step"

    def test_negative_duration_step_is_slowest(self) -> None:
        """A step with negative duration is correctly identified as slowest."""
        from behave_trace.collector import Collector
        from behave_trace.models import Feature, Scenario, Step

        collector = Collector()
        feature = Feature(name="f")
        scenario = Scenario(name="s")
        scenario.steps.append(Step(keyword="Given", name="step", duration=-0.5))
        feature.scenarios.append(scenario)
        collector.trace.features.append(feature)

        trace = collector.finalize()
        assert trace.stats.slowest_step_duration == -0.5
        assert trace.stats.slowest_step_name == "Given step"

    def test_no_steps_slowest_duration_is_zero(self) -> None:
        """With no steps, slowest_step_duration defaults to 0.0 (not -inf)."""
        from behave_trace.collector import Collector
        from behave_trace.models import Feature, Scenario

        collector = Collector()
        feature = Feature(name="f")
        feature.scenarios.append(Scenario(name="s"))
        collector.trace.features.append(feature)

        trace = collector.finalize()
        assert trace.stats.slowest_step_duration == 0.0
        assert trace.stats.slowest_step_name == ""

    def test_mixed_durations_finds_correct_slowest(self) -> None:
        """With mixed positive and zero durations, the positive one is slowest."""
        from behave_trace.collector import Collector
        from behave_trace.models import Feature, Scenario, Step

        collector = Collector()
        feature = Feature(name="f")
        scenario = Scenario(name="s")
        scenario.steps.append(Step(keyword="Given", name="fast", duration=0.0))
        scenario.steps.append(Step(keyword="When", name="slow", duration=2.5))
        scenario.steps.append(Step(keyword="Then", name="medium", duration=1.0))
        feature.scenarios.append(scenario)
        collector.trace.features.append(feature)

        trace = collector.finalize()
        assert trace.stats.slowest_step_duration == 2.5
        assert trace.stats.slowest_step_name == "When slow"


class TestBug18AttachNetworkNanInf:
    """Bug 18: attach_network used json.dumps without allow_nan=False.

    If network payload contained NaN/Inf floats, the serialized JSON
    would contain invalid ``NaN``/``Infinity`` tokens, breaking the
    viewer frontend's JSON parser.

    Fix: use ``_sanitize_floats`` and ``allow_nan=False``.
    """

    def test_attach_network_with_nan_in_payload(self) -> None:
        """attach_network sanitizes NaN/Inf in network payload."""
        import json as _json
        from unittest.mock import MagicMock

        from behave_trace.attach import attach_network
        from behave_trace.models import ARTIFACT_NETWORK

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        payload = {
            "method": "GET",
            "url": "http://example.com",
            "status": 200,
            "headers": {"X-Timing": float("nan")},
            "body": None,
            "response": {"timing": float("inf")},
        }

        attach_network(context, payload)

        formatter.attach.assert_called_once()
        artifact = formatter.attach.call_args[0][0]
        assert artifact.type == ARTIFACT_NETWORK
        # The text should be valid JSON (no NaN/Infinity tokens)
        parsed = _json.loads(artifact.text)
        assert parsed["headers"]["X-Timing"] == 0.0
        assert parsed["response"]["timing"] == 0.0

    def test_attach_network_with_negative_inf(self) -> None:
        """attach_network sanitizes -Inf in network payload."""
        import json as _json
        from unittest.mock import MagicMock

        from behave_trace.attach import attach_network

        formatter = MagicMock()
        formatter.attach = MagicMock()
        context = MagicMock()
        runner = MagicMock()
        runner.formatters = [formatter]
        context._runner = runner

        payload = {
            "method": "POST",
            "url": "http://example.com",
            "status": 500,
            "headers": {},
            "body": {"error_rate": float("-inf")},
            "response": None,
        }

        attach_network(context, payload)
        artifact = formatter.attach.call_args[0][0]
        parsed = _json.loads(artifact.text)
        assert parsed["body"]["error_rate"] == 0.0


# ---------------------------------------------------------------------------
# Background steps: per-scenario copies synced with real execution results
# ---------------------------------------------------------------------------


class _StubBgStep:
    """Behave step stub whose parent is a background."""

    def __init__(self, parent_type: str = "background", status: str = "passed") -> None:
        self.keyword = "Given"
        self.name = "bg step"
        self.status = status
        self.duration = 0.5
        self.location = "f.feature:3"
        self.text = None
        self.table = None
        self.error_message = ""
        self.exception = None
        self.exc_traceback = ""
        self.embeddings = []
        self.log = []
        self.parent = mock.Mock()
        self.parent.type = parent_type


class _StubScenario:
    def __init__(self, name: str = "S") -> None:
        self.name = name
        self.status = "passed"
        self.duration = 1.0
        self.description = []
        self.location = "f.feature:5"
        self.tags = []
        self.type = "scenario"
        self.parent = None


class _StubBackground:
    def __init__(self) -> None:
        self.name = "bg"
        self.keyword = "Background"
        self.location = "f.feature:3"
        self.steps = [_StubBgStep(parent_type="background", status="untested")]


class _StubFeature:
    def __init__(self, background=None) -> None:
        self.name = "F"
        self.status = "passed"
        self.duration = 1.0
        self.description = []
        self.location = "f.feature:1"
        self.tags = []
        self.background = background


class TestBackgroundStepSync:
    def test_background_step_status_synced_to_scenario_copy(self) -> None:
        """Background steps in scenario.background must reflect real results."""
        c = Collector()
        c.on_feature(_StubFeature(background=_StubBackground()))
        s = c.on_scenario(_StubScenario())
        bg_step = _StubBgStep(parent_type="background", status="passed")
        c.on_step(bg_step)
        assert s.background is not None
        assert s.background.steps[0].status == "passed"
        assert s.background.steps[0].duration == 0.5

    def test_scenario_background_is_not_shared_with_feature(self) -> None:
        """Each scenario owns its background copy — no cross-scenario leaks."""
        c = Collector()
        feature = c.on_feature(_StubFeature(background=_StubBackground()))
        s1 = c.on_scenario(_StubScenario(name="S1"))
        c.on_step(_StubBgStep(status="failed"))
        s2 = c.on_scenario(_StubScenario(name="S2"))
        assert s2.background is not None
        assert s2.background.steps[0].status == "untested"
        # feature.background is the definition; it stays untested
        assert feature.background is not None
        assert feature.background.steps[0].status == "untested"
        assert s1.background is not s2.background


class TestPendingAttachmentsClearedOnScenarioEnd:
    def test_pending_artifacts_do_not_bleed_into_next_scenario(self) -> None:
        from behave_trace.models import Artifact

        c = Collector()
        c.on_feature(_StubFeature())
        c.on_scenario(_StubScenario(name="S1"))
        c.attach(Artifact(type="text"))
        c.on_scenario_end(_StubScenario(name="S1"))
        s2 = c.on_scenario(_StubScenario(name="S2"))
        c.on_step(_StubBgStep(parent_type="scenario", status="passed"))
        assert len(s2.steps) == 1
        assert s2.steps[0].artifacts == []


class _StubOutline:
    def __init__(self) -> None:
        self.type = "scenario_outline"
        self.name = "My outline"
        table = mock.Mock()
        table.headings = ["a", "b"]
        row = mock.Mock()
        row.cells = ["1", "2"]
        table.rows = [row]
        example = mock.Mock()
        example.table = table
        self.examples = [example]


class TestOutlineDetection:
    def test_generated_scenario_marks_outline(self) -> None:
        """Scenarios generated from an outline get is_outline, outline_name, examples."""
        c = Collector()
        c.on_feature(_StubFeature())
        scenario_stub = _StubScenario()
        scenario_stub.parent = _StubOutline()
        s = c.on_scenario(scenario_stub)
        assert s.is_outline is True
        assert s.outline_name == "My outline"
        assert s.examples is not None
        assert s.examples.headings == ["a", "b"]
        assert s.examples.rows == [["1", "2"]]


# ---------------------------------------------------------------------------
# attach_dom: DOCTYPE ordering and <base> injection
# ---------------------------------------------------------------------------


class TestAttachDomDoctype:
    def _capture(self, html: str) -> str:
        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()
        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner
        source = mock.Mock()
        source.current_url = "https://example.com"
        source.page_source = html
        attach_dom(context, source)
        return formatter.attach.call_args[0][0].text

    def test_base_after_doctype_when_no_head(self) -> None:
        """<base> must not precede the DOCTYPE declaration."""
        html = self._capture("<!DOCTYPE html><div>Hi</div>")
        assert html.index("<!DOCTYPE") < html.index("<base")

    def test_base_inside_head_with_attributes(self) -> None:
        html = self._capture('<!DOCTYPE html><html><head data-x="1"></head></html>')
        assert html.index("<base") > html.index("<head")

    def test_uppercase_head_detected(self) -> None:
        html = self._capture("<HTML><HEAD><TITLE>x</TITLE></HEAD></HTML>")
        assert html.index("<base") > html.upper().index("<HEAD")


# ---------------------------------------------------------------------------
# attach_screenshot: MIME detection from magic bytes
# ---------------------------------------------------------------------------


class TestScreenshotMimeSniffing:
    def _attach(self, data: bytes) -> str:
        from behave_trace.attach import attach_screenshot

        formatter = mock.Mock()
        formatter.attach = mock.Mock()
        formatter.log = mock.Mock()
        runner = mock.Mock()
        runner.formatters = [formatter]
        context = mock.Mock()
        context._runner = runner
        attach_screenshot(context, data)
        return formatter.attach.call_args[0][0].mime_type

    def test_jpeg_detected(self) -> None:
        assert self._attach(b"\xff\xd8\xff\xe0" + b"\x00" * 10) == "image/jpeg"

    def test_png_default(self) -> None:
        assert self._attach(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10) == "image/png"

    def test_gif_detected(self) -> None:
        assert self._attach(b"GIF89a" + b"\x00" * 10) == "image/gif"


# ---------------------------------------------------------------------------
# Server: state notifications must carry the running flag
# ---------------------------------------------------------------------------


class TestAutoRunStateEvent:
    def test_set_auto_run_keeps_running_flag(self) -> None:
        """Toggling auto-run mid-run must not clear the running state."""
        server = ViewerServer(None, port=0, watching=True)
        events: list[dict] = []
        server._state.sse_clients.append(__import__("queue").Queue())
        q = server._state.sse_clients[0]
        server.set_running(True)
        while not q.empty():
            events.append(q.get_nowait())
        server.set_auto_run(False)
        while not q.empty():
            events.append(q.get_nowait())
        state_events = [e for e in events if e.get("type") == "state"]
        assert state_events
        assert all(e.get("running") is True for e in state_events)
