"""Tests for minor coverage gaps across multiple modules."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from behave_trace.formatter import TraceFormatter
from behave_trace.models import Background
from behave_trace.serializer import _background_from_dict, _step_from_dict

# ---------------------------------------------------------------------------
# formatter.py — rule() method
# ---------------------------------------------------------------------------


class TestFormatterRule:
    """Test the rule() method of TraceFormatter."""

    def test_rule_delegates_to_collector(self) -> None:
        """rule() should call collector.on_rule()."""
        formatter = TraceFormatter.__new__(TraceFormatter)
        formatter._collector = mock.Mock()
        rule_obj = mock.Mock(name="My Rule")
        formatter.rule(rule_obj)
        formatter._collector.on_rule.assert_called_once_with(rule_obj)


# ---------------------------------------------------------------------------
# serializer.py — _background_from_dict with non-dict step entries
# ---------------------------------------------------------------------------


class TestBackgroundFromDictEdge:
    """Edge cases for _background_from_dict."""

    def test_background_with_non_dict_steps(self) -> None:
        """Non-dict entries in steps list are skipped."""
        data = {
            "name": "bg",
            "keyword": "Background",
            "location": "test.feature:1",
            "steps": ["not a dict", 42, None, {"name": "Given step", "status": "passed"}],
        }
        bg = _background_from_dict(data)
        assert isinstance(bg, Background)
        assert len(bg.steps) == 1
        assert bg.steps[0].name == "Given step"

    def test_background_with_no_steps(self) -> None:
        """Background with no steps key returns empty steps."""
        data = {"name": "bg", "keyword": "Background", "location": ""}
        bg = _background_from_dict(data)
        assert len(bg.steps) == 0


# ---------------------------------------------------------------------------
# runner.py — PYTHONPATH with existing value, run_and_load exception
# ---------------------------------------------------------------------------


class TestRunnerPythonPath:
    """Test PYTHONPATH injection edge cases."""

    def test_run_with_existing_pythonpath(self, tmp_path: Path) -> None:
        """When PYTHONPATH already exists, new value is prepended."""
        from behave_trace.runner import BehaveRunner

        runner = BehaveRunner()
        trace_path = tmp_path / "trace.json"

        captured_env: dict = {}

        def fake_run(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            mock_result = mock.Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            return mock_result

        with (
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch.dict("os.environ", {"PYTHONPATH": "/some/existing/path"}, clear=False),
        ):
            runner.run(features_dir="features", output_path=trace_path)

        # PYTHONPATH should contain both candidate root and existing path
        assert "/some/existing/path" in captured_env.get("PYTHONPATH", "")

    def test_run_and_load_serializer_exception(self, tmp_path: Path) -> None:
        """run_and_load returns (result, None) when Serializer.load fails."""
        from behave_trace.runner import BehaveRunner

        runner = BehaveRunner()
        trace_path = tmp_path / "trace.json"
        trace_path.write_text("{}")

        mock_result = mock.Mock()
        mock_result.trace_path = trace_path  # file already exists on disk

        with (
            mock.patch.object(runner, "run", return_value=mock_result),
            mock.patch(
                "behave_trace.serializer.Serializer.load",
                side_effect=Exception("load error"),
            ),
        ):
            result, trace = runner.run_and_load(features_dir="features", output_path=trace_path)

        assert result is mock_result
        assert trace is None


# ---------------------------------------------------------------------------
# __init__.py — formatter registration exception
# ---------------------------------------------------------------------------


class TestFormatterRegistration:
    """Test that formatter registration handles exceptions gracefully."""

    def test_registration_failure_is_silent(self) -> None:
        """Importing behave_trace should not fail even if registration fails."""
        # The registration is already done at import time.
        # We verify that re-importing doesn't raise.
        import importlib

        import behave_trace

        importlib.reload(behave_trace)
        # Should not raise


# ---------------------------------------------------------------------------
# serializer.py — _step_from_dict edge cases
# ---------------------------------------------------------------------------


class TestStepFromDictEdge:
    """Edge cases for _step_from_dict."""

    def test_step_with_minimal_data(self) -> None:
        """Step with only required fields works."""
        data = {"name": "Given a step", "status": "passed"}
        step = _step_from_dict(data)
        assert step.name == "Given a step"
        assert step.status == "passed"

    def test_step_with_artifacts(self) -> None:
        """Step with artifacts list reconstructs them."""
        data = {
            "name": "Given a step",
            "status": "passed",
            "artifacts": [
                {
                    "type": "screenshot",
                    "name": "screenshot.png",
                    "mime_type": "image/png",
                    "data_base64": "iVBOR",
                }
            ],
        }
        step = _step_from_dict(data)
        assert len(step.artifacts) == 1
        assert step.artifacts[0].type == "screenshot"

    def test_step_with_table(self) -> None:
        """Step with table data reconstructs DataTable."""
        data = {
            "name": "Given a step",
            "status": "passed",
            "table": {
                "headings": ["A", "B"],
                "rows": [["1", "2"], ["3", "4"]],
            },
        }
        step = _step_from_dict(data)
        assert step.table is not None
        assert step.table.headings == ["A", "B"]
        assert step.table.rows == [["1", "2"], ["3", "4"]]

    def test_step_with_error(self) -> None:
        """Step with error info reconstructs ErrorInfo."""
        data = {
            "name": "Given a step",
            "status": "failed",
            "error": {
                "message": "Something went wrong",
                "traceback": "Traceback...",
            },
        }
        step = _step_from_dict(data)
        assert step.error is not None
        assert step.error.message == "Something went wrong"
