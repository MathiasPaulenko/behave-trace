"""Collects Behave events and builds a :class:`Trace` tree.

Decoupled from Behave's internals: accepts loosely-typed objects with
the well-known attributes Behave exposes, keeping this layer easy to
unit-test with simple stubs.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

from .models import (
    ARTIFACT_DOM,
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    LOG_INFO,
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
    normalize_level,
    normalize_status,
)
from .utils import safe_float, safe_str


def _join_description(value: Any) -> str:
    """Join a description value into a single string.

    Behave normally provides ``description`` as a list of strings (lines),
    but some stubs or alternative runners may provide a plain string.
    A bare string must not be iterated character-by-character.
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value
    try:
        return "\n".join(safe_str(d) for d in value)
    except TypeError:
        return safe_str(value)


def _safe_iterable(value: Any) -> list[Any]:
    """Return *value* as a list, or an empty list if not iterable.

    Unlike ``_as_list`` in serializer.py, this handles non-list values
    (e.g. integers, None) by returning ``[]`` instead of raising.
    """
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def _safe_attr_str(value: Any) -> str:
    """Convert a value to string, treating None as empty string.

    Unlike ``safe_str``, which would turn None into "None",
    this returns "" for None while preserving falsy values like 0 and False.
    """
    if value is None:
        return ""
    return safe_str(value)


class Collector:
    """Builds a :class:`Trace` from formatter events.

    Keeps minimal state: the root :class:`Trace`, the current feature,
    the current rule name (Gherkin v6), and the current scenario.
    """

    def __init__(self) -> None:
        self.trace = Trace()
        self.trace.environment = self._capture_environment()
        self.trace.stats = TraceStats(start_time=datetime.now())
        self._current_feature: Feature | None = None
        self._current_rule_name: str = ""
        self._current_scenario: Scenario | None = None
        self._pending_artifacts: list[Artifact] = []
        self._pending_logs: list[dict[str, Any]] = []
        self._started_scenarios = 0
        self._completed_scenarios = 0
        self._progress_url = os.environ.get("BEHAVE_TRACE_SERVER_URL")

    # ------------------------------------------------------------------
    # Environment capture
    # ------------------------------------------------------------------

    @staticmethod
    def _capture_environment() -> Environment:
        """Capture runtime environment metadata."""
        try:
            from behave import __version__ as behave_version
        except Exception:
            behave_version = "unknown"

        from . import __version__ as trace_version

        try:
            cpu_count = os.cpu_count() or 0
        except Exception:
            cpu_count = 0

        try:
            user = getpass.getuser()
        except Exception:
            user = ""

        try:
            hostname = socket.gethostname()
        except Exception:
            hostname = ""

        git_info = Collector._capture_git_info()

        return Environment(
            python_version=sys.version.split()[0],
            behave_version=behave_version,
            behave_trace_version=trace_version,
            platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
            hostname=hostname,
            cwd=safe_str(os.getcwd()),
            command=" ".join(sys.argv),
            user=user,
            cpu_count=cpu_count,
            git_branch=git_info.get("branch", ""),
            git_commit=git_info.get("commit", ""),
            git_remote=git_info.get("remote", ""),
        )

    @staticmethod
    def _capture_git_info() -> dict[str, str]:
        """Capture git branch, commit and remote if available."""
        info: dict[str, str] = {}
        try:
            for key, cmd in [
                ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                ("commit", ["git", "rev-parse", "--short", "HEAD"]),
                ("remote", ["git", "remote", "get-url", "origin"]),
            ]:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0:
                    info[key] = result.stdout.strip()
        except Exception:
            pass
        return info

    # ------------------------------------------------------------------
    # Feature lifecycle
    # ------------------------------------------------------------------

    def on_feature(self, behave_feature: Any) -> Feature:
        """Start a new feature."""
        feature = Feature(
            name=_safe_attr_str(getattr(behave_feature, "name", None)),
            description=_join_description(getattr(behave_feature, "description", [])),
            location=safe_str(getattr(behave_feature, "location", "")),
            tags=[safe_str(t) for t in _safe_iterable(getattr(behave_feature, "tags", []))],
        )
        bg = getattr(behave_feature, "background", None)
        if bg:
            feature.background = self._make_background(bg)
        self._current_feature = feature
        self.trace.features.append(feature)
        return feature

    def on_feature_end(self, behave_feature: Any) -> None:
        """Finalize the current feature with its final status and duration."""
        if self._current_feature is None:
            return
        self._current_feature.status = normalize_status(getattr(behave_feature, "status", None))
        self._current_feature.duration = safe_float(getattr(behave_feature, "duration", 0.0) or 0.0)
        self._current_feature = None
        self._current_rule_name = ""

    # ------------------------------------------------------------------
    # Rule (Gherkin v6 / Behave 1.3.x)
    # ------------------------------------------------------------------

    def on_rule(self, behave_rule: Any) -> None:
        self._current_rule_name = _safe_attr_str(getattr(behave_rule, "name", None))

    # ------------------------------------------------------------------
    # Scenario lifecycle
    # ------------------------------------------------------------------

    def on_scenario(self, behave_scenario: Any) -> Scenario:
        """Start a new scenario."""
        scenario_type = safe_str(getattr(behave_scenario, "type", ""))
        is_outline = scenario_type in ("scenario_outline", "outline")

        scenario = Scenario(
            name=_safe_attr_str(getattr(behave_scenario, "name", None)),
            description=_join_description(getattr(behave_scenario, "description", [])),
            location=safe_str(getattr(behave_scenario, "location", "")),
            tags=[safe_str(t) for t in _safe_iterable(getattr(behave_scenario, "tags", []))],
            feature_name=self._current_feature.name if self._current_feature else "",
            rule_name=self._current_rule_name,
            is_outline=is_outline,
            outline_name="",
            examples=None,
        )
        if self._current_feature and self._current_feature.background:
            scenario.background = self._current_feature.background
        self._current_scenario = scenario
        if self._current_feature is not None:
            self._current_feature.scenarios.append(scenario)
        self._started_scenarios += 1
        self._post_progress("scenario_started", scenario.name)
        return scenario

    def on_scenario_end(self, behave_scenario: Any) -> None:
        """Finalize the current scenario."""
        if self._current_scenario is None:
            return
        self._current_scenario.status = normalize_status(getattr(behave_scenario, "status", None))
        self._current_scenario.duration = safe_float(
            getattr(behave_scenario, "duration", 0.0) or 0.0
        )
        self._completed_scenarios += 1
        self._post_progress("scenario_completed", self._current_scenario.name)
        self._current_scenario = None

    def _post_progress(self, event: str, scenario_name: str) -> None:
        """Notify the viewer server of scenario progress via HTTP POST."""
        if not self._progress_url:
            return
        url = f"{self._progress_url}/api/progress"
        payload = json.dumps(
            {
                "event": event,
                "scenario_name": scenario_name,
                "completed": self._completed_scenarios,
                "total": self._started_scenarios,
            }
        ).encode()
        try:
            req = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=1):
                pass
        except Exception:
            # Server may be unavailable; don't fail the test run
            pass

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def on_step(self, behave_step: Any) -> Step | None:
        """Add a step result to the current scenario.

        Flushes any pending artifacts and logs that were captured during
        step execution (via attach_screenshot, attach_dom, log, etc.)
        onto this step.
        """
        if self._current_scenario is None:
            self._pending_artifacts.clear()
            self._pending_logs.clear()
            return None
        step = self._make_step(behave_step)
        step.artifacts.extend(self._pending_artifacts)
        step.logs.extend(self._pending_logs)
        self._pending_artifacts.clear()
        self._pending_logs.clear()
        self._current_scenario.steps.append(step)
        return step

    def _make_step(self, behave_step: Any) -> Step:
        """Convert a Behave step object into a Step model."""
        raw_text = getattr(behave_step, "text", None)
        step = Step(
            keyword=_safe_attr_str(getattr(behave_step, "keyword", None)).strip(),
            name=_safe_attr_str(getattr(behave_step, "name", None)),
            status=normalize_status(getattr(behave_step, "status", None)),
            duration=safe_float(getattr(behave_step, "duration", 0.0) or 0.0),
            location=safe_str(getattr(behave_step, "location", "")),
            text=safe_str(raw_text) if raw_text is not None else None,
        )

        # Data table
        table = getattr(behave_step, "table", None)
        if table is not None:
            try:
                step.table = DataTable(
                    headings=[safe_str(h) for h in getattr(table, "headings", []) or []],
                    rows=[[safe_str(c) for c in row.cells] for row in table.rows],
                )
            except Exception:
                step.table = None

        # Error info
        error_message = _safe_attr_str(getattr(behave_step, "error_message", None))
        exception = getattr(behave_step, "exception", None)
        if error_message or exception:
            step.error = ErrorInfo(
                message=safe_str(error_message or exception),
                traceback=safe_str(getattr(behave_step, "exc_traceback", "") or error_message),
                exception_type=type(exception).__name__ if exception else "",
            )

        # Embeddings → artifacts (behave-kit attach() or native embeddings)
        for embedding in _safe_iterable(getattr(behave_step, "embeddings", [])):
            artifact = self._make_artifact(embedding)
            if artifact:
                step.artifacts.append(artifact)

        # Logs
        step.logs = [safe_str(line) for line in _safe_iterable(getattr(behave_step, "log", []))]
        return step

    def _make_artifact(self, embedding: Any) -> Artifact | None:
        """Convert a Behave embedding into an Artifact."""
        mime_type = _safe_attr_str(getattr(embedding, "mime_type", None))
        name = _safe_attr_str(getattr(embedding, "name", None))
        data_base64 = _safe_attr_str(getattr(embedding, "data", None))

        if not data_base64 and not name:
            return None

        artifact_type = ARTIFACT_TEXT
        if mime_type.startswith("image/"):
            artifact_type = ARTIFACT_SCREENSHOT
        elif mime_type == "text/html":
            artifact_type = ARTIFACT_DOM
        elif name.lower().startswith("screenshot"):
            artifact_type = ARTIFACT_SCREENSHOT
        elif name.lower().startswith("dom"):
            artifact_type = ARTIFACT_DOM

        return Artifact(
            type=artifact_type,
            name=name,
            mime_type=mime_type or "application/octet-stream",
            data_base64=data_base64,
        )

    def _make_background(self, behave_background: Any) -> Background:
        """Convert a Behave background object into a Background model."""
        bg = Background(
            name=_safe_attr_str(getattr(behave_background, "name", None)),
            keyword=_safe_attr_str(getattr(behave_background, "keyword", None)) or "Background",
            location=safe_str(getattr(behave_background, "location", "")),
        )
        for behave_step in _safe_iterable(getattr(behave_background, "steps", [])):
            bg.steps.append(self._make_step(behave_step))
        return bg

    # ------------------------------------------------------------------
    # Attachment API (for environment.py hooks via attach.py)
    # ------------------------------------------------------------------

    def attach(self, artifact: Artifact) -> None:
        """Queue an artifact to be attached to the current step.

        Artifacts are buffered and flushed onto the step when
        :meth:`on_step` is called (after step execution completes).
        """
        self._pending_artifacts.append(artifact)

    def log(self, message: str, level: str = LOG_INFO) -> None:
        """Queue a log line to be attached to the current step.

        Logs are buffered and flushed onto the step when
        :meth:`on_step` is called (after step execution completes).

        Args:
            message: The log message text.
            level: Log level — "info", "warning", or "error".
        """
        entry: dict[str, Any] = {
            "level": normalize_level(level),
            "message": safe_str(message),
            "timestamp": datetime.now().isoformat(),
        }
        self._pending_logs.append(entry)

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def finalize(self) -> Trace:
        """Finalize the trace tree and compute statistics."""
        self.trace.stats.end_time = datetime.now()
        self._compute_stats()
        return self.trace

    def _compute_stats(self) -> None:
        """Compute aggregate statistics from the trace tree."""
        stats = self.trace.stats
        stats.total_features = len(self.trace.features)
        stats.total_scenarios = sum(len(f.scenarios) for f in self.trace.features)
        stats.total_steps = sum(len(s.steps) for f in self.trace.features for s in f.scenarios)
        stats.duration = sum(f.duration for f in self.trace.features)

        by_status: dict[str, int] = {}
        total_artifacts = 0
        total_screenshots = 0
        total_logs = 0
        all_step_durations: list[float] = []
        slowest_duration = float("-inf")
        slowest_name = ""

        for feature in self.trace.features:
            for scenario in feature.scenarios:
                by_status[scenario.status] = by_status.get(scenario.status, 0) + 1
                for step in scenario.steps:
                    all_step_durations.append(step.duration)
                    if step.duration > slowest_duration:
                        slowest_duration = step.duration
                        slowest_name = f"{step.keyword} {step.name}"
                    total_artifacts += len(step.artifacts)
                    total_screenshots += sum(
                        1 for a in step.artifacts if a.type == ARTIFACT_SCREENSHOT
                    )
                    total_logs += len(step.logs)

        stats.by_status = by_status
        stats.total_artifacts = total_artifacts
        stats.total_screenshots = total_screenshots
        stats.total_logs = total_logs
        stats.slowest_step_duration = slowest_duration if slowest_duration != float("-inf") else 0.0
        stats.slowest_step_name = slowest_name
        if all_step_durations:
            stats.avg_step_duration = sum(all_step_durations) / len(all_step_durations)
