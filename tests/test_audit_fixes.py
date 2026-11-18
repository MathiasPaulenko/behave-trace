"""Regression tests for audit-cycle fixes.

Covers: Behave status aliasing, steps skipped without a ``result()`` event,
watch-mode pending runs, server CSRF/origin checks, ``/api/source``
allowlist and size cap, ``/api/rerun`` validation, watcher deletions,
duration boundaries, DOM ``<base>`` injection, atomic trace saves, and
git remote credential stripping.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from behave_trace.collector import Collector, _sanitize_git_remote
from behave_trace.models import Trace, normalize_status
from behave_trace.serializer import Serializer
from behave_trace.utils import format_duration
from behave_trace.viewer.server import ViewerServer


def _post(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode()


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class StubStep:
    keyword: str = "Given"
    name: str = "step"
    status: str = "passed"
    duration: float = 0.1
    location: str = "steps.py:10"
    error_message: str = ""
    exception: Any = None


@dataclass
class StubScenario:
    name: str = "Scenario"
    status: str = "failed"
    duration: float = 0.5
    description: list[str] = field(default_factory=list)
    location: str = "f.feature:5"
    tags: list[str] = field(default_factory=list)
    type: str = "scenario"
    steps: list[Any] = field(default_factory=list)
    background_steps: list[Any] = field(default_factory=list)

    @property
    def all_steps(self) -> list[Any]:
        return [*self.background_steps, *self.steps]


@dataclass
class StubBackground:
    name: str = ""
    keyword: str = "Background"
    location: str = "f.feature:3"
    steps: list[Any] = field(default_factory=list)


@dataclass
class StubFeature:
    name: str = "Feature"
    status: str = "passed"
    duration: float = 1.0
    description: list[str] = field(default_factory=list)
    location: str = "f.feature:1"
    tags: list[str] = field(default_factory=list)
    background: Any = None


# ---------------------------------------------------------------------------
# normalize_status — Behave Status enum aliasing
# ---------------------------------------------------------------------------


class TestNormalizeStatusAliases:
    """Behave Status values without a canonical name must not degrade
    to ``untested`` — an unexpected exception must show as failed."""

    def test_error_statuses_map_to_failed(self) -> None:
        for name in ("error", "hook_error", "cleanup_error", "pending"):
            assert normalize_status(name) == "failed", name

    def test_pending_warn_and_expected_map_to_passed(self) -> None:
        for name in ("pending_warn", "xfailed", "xpassed"):
            assert normalize_status(name) == "passed", name

    def test_executing_maps_to_running(self) -> None:
        assert normalize_status("executing") == "running"

    def test_untested_variants(self) -> None:
        assert normalize_status("untested_undefined") == "undefined"
        assert normalize_status("untested_pending") == "undefined"

    def test_real_behave_status_enum(self) -> None:
        """Real enum objects — the exact type Behave passes at runtime."""
        behave = pytest.importorskip("behave.model_type")
        assert normalize_status(behave.Status.error) == "failed"
        assert normalize_status(behave.Status.hook_error) == "failed"
        assert normalize_status(behave.Status.cleanup_error) == "failed"
        assert normalize_status(behave.Status.pending) == "failed"
        assert normalize_status(behave.Status.executing) == "running"
        assert normalize_status(behave.Status.failed) == "failed"
        assert normalize_status(behave.Status.passed) == "passed"
        assert normalize_status(behave.Status.skipped) == "skipped"
        assert normalize_status(behave.Status.undefined) == "undefined"
        assert normalize_status(behave.Status.untested) == "untested"

    def test_unknown_status_still_untested(self) -> None:
        assert normalize_status("something_new") == "untested"
        assert normalize_status(None) == "untested"


# ---------------------------------------------------------------------------
# Steps skipped without result() event
# ---------------------------------------------------------------------------


class TestFlushMissingSteps:
    """Behave marks steps after a failure as skipped without emitting
    ``result()``. The collector must record them at scenario end."""

    def test_skipped_tail_steps_recorded(self) -> None:
        c = Collector()
        c.on_feature(StubFeature())
        steps = [
            StubStep(name="passes", status="passed"),
            StubStep(name="fails", status="failed"),
            StubStep(name="skipped1", status="skipped"),
            StubStep(name="skipped2", status="skipped"),
        ]
        scen = StubScenario(steps=steps)
        c.on_scenario(scen)
        # Behave only emits result() for executed steps
        c.on_step(steps[0])
        c.on_step(steps[1])
        c.on_scenario_end(scen)

        got = [s.name for s in c.trace.features[0].scenarios[0].steps]
        assert got == ["passes", "fails", "skipped1", "skipped2"]
        statuses = [s.status for s in c.trace.features[0].scenarios[0].steps]
        assert statuses == ["passed", "failed", "skipped", "skipped"]

    def test_background_missing_steps_synced(self) -> None:
        c = Collector()
        bg_steps = [StubStep(name="bg1", status="passed")]
        c.on_feature(StubFeature(background=StubBackground(steps=bg_steps)))
        scen = StubScenario(
            steps=[StubStep(name="s1", status="skipped")],
            background_steps=bg_steps,
        )
        c.on_scenario(scen)
        # Nothing emitted result() — both background and scenario steps flushed
        c.on_scenario_end(scen)

        scenario = c.trace.features[0].scenarios[0]
        assert [s.name for s in scenario.steps] == ["bg1", "s1"]
        assert scenario.background is not None
        assert scenario.background.steps[0].name == "bg1"
        assert scenario.background.steps[0].status == "passed"

    def test_no_duplicate_steps_when_all_reported(self) -> None:
        c = Collector()
        c.on_feature(StubFeature())
        steps = [StubStep(name=f"s{i}", status="passed") for i in range(3)]
        scen = StubScenario(steps=steps)
        c.on_scenario(scen)
        for s in steps:
            c.on_step(s)
        c.on_scenario_end(scen)

        assert len(c.trace.features[0].scenarios[0].steps) == 3

    def test_scenario_without_all_steps_attr(self) -> None:
        """Stubs/objects lacking all_steps must not crash the flush."""
        c = Collector()
        c.on_feature(StubFeature())

        @dataclass
        class MinimalScenario:
            name: str = "S"
            status: str = "passed"

        c.on_scenario(MinimalScenario())
        c.on_step(StubStep(name="only", status="passed"))
        c.on_scenario_end(MinimalScenario())

        steps = c.trace.features[0].scenarios[0].steps
        assert [s.name for s in steps] == ["only"]

    def test_double_result_same_step_not_duplicated(self) -> None:
        c = Collector()
        c.on_feature(StubFeature())
        scen = StubScenario()
        c.on_scenario(scen)
        step = StubStep(name="dup", status="passed")
        c.on_step(step)
        c.on_step(step)  # same object twice
        c.on_scenario_end(scen)
        assert len(c.trace.features[0].scenarios[0].steps) == 1


# ---------------------------------------------------------------------------
# Watch-mode pending runs (request_run / finish_run)
# ---------------------------------------------------------------------------


class TestPendingRuns:
    def test_request_run_queues_while_running(self) -> None:
        """File changes during a run must queue a follow-up, not be dropped."""
        server = ViewerServer(Trace(), port=0)
        assert server.request_run() is True
        assert server.request_run() is False  # busy → queued
        assert server.request_run() is False  # busy → queued
        assert server.finish_run() == 2  # two pending requests
        assert server.is_running() is True  # still running, caller must loop
        assert server.finish_run() == 0
        assert server.is_running() is False

    def test_set_running_false_clears_pending(self) -> None:
        server = ViewerServer(Trace(), port=0)
        assert server.request_run() is True
        server.request_run()  # queues one
        server.set_running(False)  # external stop wins over pending queue
        assert server.finish_run() == 0
        assert server.is_running() is False

    def test_try_set_running_still_works(self) -> None:
        server = ViewerServer(Trace(), port=0)
        assert server.try_set_running(True) is True
        assert server.try_set_running(True) is False
        server.set_running(False)
        assert server.try_set_running(True) is True
        server.set_running(False)


# ---------------------------------------------------------------------------
# Server hardening: Origin check, /api/source allowlist, /api/rerun
# ---------------------------------------------------------------------------


class TestServerHardening:
    def test_post_with_foreign_origin_rejected(self) -> None:
        """CSRF: a browser page on another origin must not trigger runs."""
        trace = Trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda n: None)
        server.start()
        try:
            status, _, body = _post(
                f"{server.url}/api/run",
                {},
                headers={"Origin": "https://evil.example.com"},
            )
            assert status == 403
        finally:
            server.stop()

    def test_post_with_local_origin_allowed(self) -> None:
        trace = Trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda n: None)
        server.start()
        try:
            status, _, _ = _post(
                f"{server.url}/api/autorun",
                {"enabled": False},
                headers={"Origin": server.url},
            )
            assert status == 200
        finally:
            server.stop()

    def test_post_without_origin_allowed(self) -> None:
        """Non-browser clients (urllib, curl) send no Origin."""
        trace = Trace()
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, _ = _post(f"{server.url}/api/autorun", {"enabled": True})
            assert status == 200
        finally:
            server.stop()

    def test_rerun_failed_filter_without_scenarios_400(self) -> None:
        trace = Trace()
        server = ViewerServer(trace, port=0, rerun_callback=lambda n: None)
        server.start()
        try:
            status, _, _ = _post(f"{server.url}/api/rerun", {"filter": "failed"})
            assert status == 400
            status, _, _ = _post(f"{server.url}/api/rerun", {"filter": "selected", "scenarios": []})
            assert status == 400
            status, _, _ = _post(
                f"{server.url}/api/rerun",
                {"filter": "selected", "scenarios": [None]},
            )
            assert status == 400
        finally:
            server.stop()

    def test_source_disallowed_extension(self, tmp_path: Path) -> None:
        """``/api/source`` must not serve arbitrary files (.env, keys...)."""
        secret = tmp_path / ".env"
        secret.write_text("TOKEN=abc", encoding="utf-8")
        trace = Trace()
        trace.environment.cwd = str(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, _ = _get(f"{server.url}/api/source?path=.env&line=1")
            assert status == 403
            status, _, _ = _get(f"{server.url}/api/source?path=config.ini&line=1")
            assert status == 403
        finally:
            server.stop()

    def test_source_allowed_extensions(self, tmp_path: Path) -> None:
        for name in ("steps.py", "x.feature", "notes.txt", "README.md"):
            (tmp_path / name).write_text("line1\nline2\n", encoding="utf-8")
        trace = Trace()
        trace.environment.cwd = str(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            for name in ("steps.py", "x.feature", "notes.txt", "README.md"):
                status, _, body = _get(f"{server.url}/api/source?path={name}&line=1")
                assert status == 200, name
                assert json.loads(body)["snippet"]
        finally:
            server.stop()

    def test_source_uppercase_extension(self, tmp_path: Path) -> None:
        (tmp_path / "STEPS.PY").write_text("x = 1\n", encoding="utf-8")
        trace = Trace()
        trace.environment.cwd = str(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, _ = _get(f"{server.url}/api/source?path=STEPS.PY&line=1")
            assert status == 200
        finally:
            server.stop()

    def test_source_oversized_file(self, tmp_path: Path) -> None:
        big = tmp_path / "big.py"
        big.write_text("x" * (21 * 1024 * 1024), encoding="utf-8")
        trace = Trace()
        trace.environment.cwd = str(tmp_path)
        server = ViewerServer(trace, port=0)
        server.start()
        try:
            status, _, _ = _get(f"{server.url}/api/source?path=big.py&line=1")
            assert status == 413
        finally:
            server.stop()

    def test_invalid_port_raises_oserror(self) -> None:
        server = ViewerServer(Trace(), port=99999)
        with pytest.raises(OSError, match="Invalid port"):
            server.start()
        server = ViewerServer(Trace(), port=-1)
        with pytest.raises(OSError, match="Invalid port"):
            server.start()


# ---------------------------------------------------------------------------
# CLI --port validation
# ---------------------------------------------------------------------------


class TestPortValidation:
    def test_port_out_of_range_rejected(self) -> None:
        from behave_trace.cli.app import main

        with pytest.raises(SystemExit):
            main(["show", "trace.json", "--port", "99999"])
        with pytest.raises(SystemExit):
            main(["show", "trace.json", "--port", "-5"])
        with pytest.raises(SystemExit):
            main(["run", ".", "--port", "abc"])

    def test_valid_ports_accepted(self) -> None:
        from behave_trace.cli.app import _port_arg

        assert _port_arg("0") == 0
        assert _port_arg("8080") == 8080
        assert _port_arg("65535") == 65535


# ---------------------------------------------------------------------------
# Watcher: deletions and moves
# ---------------------------------------------------------------------------


class TestWatcherDeletions:
    def test_polling_detects_deleted_file(self, tmp_path: Path) -> None:
        """A deleted .feature changes the suite and must trigger a re-run."""
        target = tmp_path / "gone.feature"
        target.write_text("Feature: x\n", encoding="utf-8")

        changed: list[list[str]] = []
        callback_event = threading.Event()

        def callback(files: list[str]) -> None:
            changed.append(files)
            callback_event.set()

        watcher = _PollingWatcher(tmp_path, callback, debounce_ms=200)
        watcher.start()
        try:
            time.sleep(0.6)  # initial snapshot
            target.unlink()
            assert callback_event.wait(timeout=10), "Deletion not detected"
            all_files = [f for batch in changed for f in batch]
            assert any("gone.feature" in f for f in all_files)
        finally:
            watcher.stop()


def _PollingWatcher(directory, callback, debounce_ms):  # noqa: N802
    """FileWatcher forced onto the polling backend (watchdog may exist)."""
    from behave_trace.watcher import FileWatcher

    watcher = FileWatcher(directory, callback, debounce_ms=debounce_ms)
    watcher._start_watchdog = lambda: (_ for _ in ()).throw(ImportError("forced"))
    return watcher


# ---------------------------------------------------------------------------
# format_duration boundaries
# ---------------------------------------------------------------------------


class TestFormatDurationBoundaries:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0.9994, "999ms"),
            (0.9999, "1.00s"),
            (1.0, "1.00s"),
            (59.994, "59.99s"),
            (59.999, "1m 0s"),
            (60.0, "1m 0s"),
            (3599.9, "1h 0m 0s"),
            (3600.0, "1h 0m 0s"),
        ],
    )
    def test_rollover_boundaries(self, seconds: float, expected: str) -> None:
        assert format_duration(seconds) == expected


# ---------------------------------------------------------------------------
# attach_dom <base> injection
# ---------------------------------------------------------------------------


class TestAttachDomBaseInjection:
    def _capture(self):
        class FakeFormatter:
            def __init__(self) -> None:
                self.artifacts: list[Any] = []

            def attach(self, artifact: Any) -> None:
                self.artifacts.append(artifact)

            def log(self, *a: Any, **kw: Any) -> None:
                pass

        @dataclass
        class FakeRunner:
            formatters: list[Any]

        @dataclass
        class FakeContext:
            _runner: Any

        fmt = FakeFormatter()
        return FakeContext(_runner=FakeRunner(formatters=[fmt])), fmt

    class _Driver:
        current_url = "https://example.com/page"

        def __init__(self, source: str) -> None:
            self.page_source = source

    def test_header_element_does_not_confuse_head_match(self) -> None:
        """``<header>`` must not be mistaken for ``<head>``."""
        from behave_trace.attach import attach_dom

        ctx, fmt = self._capture()
        html = '<html><body><header class="h">T</header><p>x</p></body></html>'
        attach_dom(ctx, self._Driver(html))

        art = fmt.artifacts[0]
        assert art.text is not None
        # base goes after <html>, never inside <header>
        assert "<base " in art.text
        assert art.text.index("<base") < art.text.index("<header")

    def test_base_inside_head(self) -> None:
        from behave_trace.attach import attach_dom

        ctx, fmt = self._capture()
        html = '<html><head lang="en"><title>T</title></head><body/></html>'
        attach_dom(ctx, self._Driver(html))

        art = fmt.artifacts[0]
        assert art.text is not None
        head_end = art.text.index('lang="en">')
        assert "<base" in art.text[head_end : head_end + 60]

    def test_no_double_base(self) -> None:
        from behave_trace.attach import attach_dom

        ctx, fmt = self._capture()
        html = '<html><head><base href="https://x/"></head></html>'
        attach_dom(ctx, self._Driver(html))
        assert fmt.artifacts[0].text.count("<base") == 1


# ---------------------------------------------------------------------------
# Serializer: atomic save
# ---------------------------------------------------------------------------


class TestAtomicSave:
    def test_save_leaves_no_tmp_files(self, tmp_path: Path) -> None:
        out = tmp_path / "trace.json"
        Serializer.save(Trace(), out)
        assert out.exists()
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []

    def test_failed_replace_keeps_original(self, tmp_path: Path) -> None:
        out = tmp_path / "trace.json"
        Serializer.save(Trace(), out)
        original = out.read_bytes()

        with (
            mock.patch("behave_trace.serializer.os.replace", side_effect=OSError("denied")),
            pytest.raises(OSError),
        ):
            Serializer.save(Trace(), out)

        assert out.read_bytes() == original  # original untouched
        assert not list(tmp_path.glob("*.tmp"))  # tmp cleaned up

    def test_concurrent_saves_same_path(self, tmp_path: Path) -> None:
        """Two threads saving the same path must not share the tmp file."""
        out = tmp_path / "trace.json"
        errors: list[BaseException] = []

        def save() -> None:
            try:
                for _ in range(25):
                    Serializer.save(Trace(), out)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=save) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert Serializer.load(out) is not None
        assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------------------
# Git remote credential stripping
# ---------------------------------------------------------------------------


class TestGitRemoteSanitize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("https://user:token@github.com/org/repo.git", "https://github.com/org/repo.git"),
            ("https://user@github.com/org/repo.git", "https://github.com/org/repo.git"),
            ("git@github.com:org/repo.git", "git@github.com:org/repo.git"),
            ("https://github.com/org/repo.git", "https://github.com/org/repo.git"),
            ("ssh://git@github.com/org/repo.git", "ssh://github.com/org/repo.git"),
        ],
    )
    def test_credentials_stripped(self, raw: str, expected: str) -> None:
        assert _sanitize_git_remote(raw) == expected

    def test_environment_git_remote_sanitized(self) -> None:
        outputs = {
            "rev-parse --abbrev-ref HEAD": "main",
            "rev-parse --short HEAD": "abc123",
            "remote get-url origin": "https://ci:SECRET@github.com/org/repo.git",
        }

        def fake_run(cmd, **kw):
            key = " ".join(cmd[1:])
            result = mock.Mock()
            result.returncode = 0
            result.stdout = outputs.get(key, "") + "\n"
            result.stderr = ""
            return result

        with mock.patch("behave_trace.collector.subprocess.run", side_effect=fake_run):
            info = Collector._capture_git_info()

        assert "SECRET" not in info["remote"]
        assert info["remote"] == "https://github.com/org/repo.git"


# ---------------------------------------------------------------------------
# CLI run: per-process trace path
# ---------------------------------------------------------------------------


class TestRunTracePath:
    def test_run_trace_path_unique_per_pid(self) -> None:
        from behave_trace.cli.app import _run_trace_path

        p = _run_trace_path()
        assert p.name == f"behave-trace-{__import__('os').getpid()}.json"

    def test_stale_trace_removed_before_run(self, tmp_path: Path) -> None:
        """A leftover trace from a crashed run must not be loaded."""
        from behave_trace.cli.app import _run_trace_path

        stale = _run_trace_path()
        stale.write_text('{"stale": true}', encoding="utf-8")
        try:
            args = argparse.Namespace(
                features_dir=str(tmp_path),
                port=0,
                no_browser=True,
                tags=None,
                watch=False,
            )
            mock_runner = mock.Mock()
            mock_result = mock.Mock(stdout="", stderr="", trace_path=None)
            mock_runner.run = mock.Mock(return_value=mock_result)

            with (
                mock.patch("behave_trace.runner.BehaveRunner", return_value=mock_runner),
                mock.patch(
                    "behave_trace.viewer.server.ViewerServer.start",
                    side_effect=OSError("stop early"),
                ),
            ):
                from behave_trace.cli.app import _cmd_run

                _cmd_run(args)

            assert not stale.exists() or json.loads(stale.read_text()) != {"stale": True}
        finally:
            stale.unlink(missing_ok=True)
