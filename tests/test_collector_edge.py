"""Edge-case tests for the Collector class."""

from __future__ import annotations

from unittest import mock
from urllib.error import URLError

from behave_trace.collector import Collector


class TestCaptureEnvironmentEdge:
    """Edge cases for _capture_environment."""

    def test_behave_import_fails(self) -> None:
        """When behave import fails, behave_version should be 'unknown'."""
        real_import = __import__

        def selective_import(name, *args, **kwargs):
            if name == "behave":
                raise ImportError("no behave")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=selective_import):
            env = Collector._capture_environment()
        assert env.behave_version == "unknown"

    def test_cpu_count_fails(self) -> None:
        """When os.cpu_count raises, cpu_count should be 0."""
        with mock.patch("os.cpu_count", side_effect=OSError):
            env = Collector._capture_environment()
        assert env.cpu_count == 0

    def test_getuser_fails(self) -> None:
        """When getpass.getuser raises, user should be empty."""
        with mock.patch("getpass.getuser", mock.Mock(side_effect=OSError)):
            env = Collector._capture_environment()
        assert env.user == ""

    def test_hostname_fails(self) -> None:
        """When socket.gethostname raises, hostname should be empty."""
        with mock.patch("socket.gethostname", side_effect=OSError):
            env = Collector._capture_environment()
        assert env.hostname == ""


class TestCaptureGitInfo:
    """Tests for _capture_git_info."""

    def test_git_not_available(self) -> None:
        """When git command fails, returns empty dict."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="error")
            info = Collector._capture_git_info()
        assert info == {}

    def test_git_subprocess_raises(self) -> None:
        """When subprocess.run raises, returns empty dict."""
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            info = Collector._capture_git_info()
        assert info == {}

    def test_git_success(self) -> None:
        """When git commands succeed, returns branch/commit/remote."""
        responses = [
            mock.Mock(returncode=0, stdout="main\n", stderr=""),
            mock.Mock(returncode=0, stdout="abc1234\n", stderr=""),
            mock.Mock(returncode=0, stdout="origin\n", stderr=""),
        ]
        with mock.patch("subprocess.run", side_effect=responses):
            info = Collector._capture_git_info()
        assert info["branch"] == "main"
        assert info["commit"] == "abc1234"
        assert info["remote"] == "origin"


class TestOnFeatureEndNoFeature:
    """Test on_feature_end when no feature is active."""

    def test_on_feature_end_without_feature(self) -> None:
        """on_feature_end should be a no-op when no feature is active."""
        collector = Collector()
        # Should not raise
        collector.on_feature_end(mock.Mock(status="passed", duration=1.0))
        assert collector.trace.features == []


class TestOnScenarioEndNoScenario:
    """Test on_scenario_end when no scenario is active."""

    def test_on_scenario_end_without_scenario(self) -> None:
        """on_scenario_end should be a no-op when no scenario is active."""
        collector = Collector()
        collector.on_scenario_end(mock.Mock(status="passed", duration=1.0))
        # Should not raise


class TestPostProgress:
    """Tests for _post_progress."""

    def test_post_progress_without_url(self) -> None:
        """_post_progress should be a no-op when no progress_url is set."""
        collector = Collector()
        collector._post_progress("scenario_started", "test")
        # No exception, no network call

    def test_post_progress_with_url_success(self) -> None:
        """_post_progress sends HTTP POST when progress_url is set."""
        with mock.patch.dict("os.environ", {"BEHAVE_TRACE_SERVER_URL": "http://127.0.0.1:9999"}):
            collector = Collector()
        with mock.patch("behave_trace.collector.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = mock.Mock()
            mock_urlopen.return_value.__exit__ = mock.Mock(return_value=False)
            collector._post_progress("scenario_started", "test")
        mock_urlopen.assert_called_once()

    def test_post_progress_with_url_failure(self) -> None:
        """_post_progress silently ignores network errors."""
        with mock.patch.dict("os.environ", {"BEHAVE_TRACE_SERVER_URL": "http://127.0.0.1:9999"}):
            collector = Collector()
        with mock.patch("behave_trace.collector.urlopen", side_effect=URLError("fail")):
            # Should not raise
            collector._post_progress("scenario_started", "test")


class TestStepTableException:
    """Test that table parsing exceptions are handled gracefully."""

    def test_table_rows_exception(self) -> None:
        """When table.rows raises, step.table should be None."""
        collector = Collector()
        # Set up a feature and scenario
        feature_mock = mock.Mock()
        feature_mock.name = "F"
        feature_mock.tags = []
        feature_mock.description = []
        feature_mock.location = ""
        feature_mock.background = None
        collector.on_feature(feature_mock)

        scenario_mock = mock.Mock()
        scenario_mock.name = "S"
        scenario_mock.tags = []
        scenario_mock.type = ""
        scenario_mock.keyword = "Scenario"
        scenario_mock.location = ""
        scenario_mock.description = []
        collector.on_scenario(scenario_mock)

        # Create a step with a table that raises on .rows
        bad_table = mock.Mock()
        bad_table.headings = ["a", "b"]
        type(bad_table).rows = mock.PropertyMock(side_effect=RuntimeError("bad"))

        step_mock = mock.Mock()
        step_mock.name = "Given a step"
        step_mock.keyword = "Given"
        step_mock.status = "passed"
        step_mock.duration = 0.1
        step_mock.error_message = ""
        step_mock.exception = None
        step_mock.text = None
        step_mock.location = ""
        step_mock.embeddings = []
        step_mock.log = []
        step_mock.table = bad_table

        step = collector.on_step(step_mock)
        assert step is not None
        assert step.table is None
