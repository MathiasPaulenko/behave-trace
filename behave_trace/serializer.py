"""Serialize and deserialize :class:`Trace` to/from JSON files.

Format: JSON (plain). The .trace extension is conventional but the
content is JSON by default.

Raises:
    FileNotFoundError: If the input file does not exist.
    json.JSONDecodeError: If the file content is not valid JSON.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
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
)


class Serializer:
    """Serialize and deserialize Trace objects."""

    @staticmethod
    def save(trace: Trace, path: str | Path) -> Path:
        """Save a trace to a JSON file.

        Args:
            trace: The Trace object to save.
            path: Output file path.

        Returns:
            The path where the trace was written.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = as_dict(trace)
        p.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        return p

    @staticmethod
    def load(path: str | Path) -> Trace:
        """Load a trace from a JSON file.

        Args:
            path: Input file path.

        Returns:
            Reconstructed Trace object.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Trace file not found: {p}")
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        return Serializer._from_dict(data)

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> Trace:
        """Reconstruct a Trace from a plain dict."""
        trace = Trace(
            version=data.get("version", "1"),
            features=[],
        )
        created = data.get("created_at")
        if created:
            with contextlib.suppress(ValueError):
                trace.created_at = datetime.fromisoformat(created)
        for f_data in data.get("features", []):
            feature = _feature_from_dict(f_data)
            trace.features.append(feature)
        env_data = data.get("environment", {})
        trace.environment = _environment_from_dict(env_data)
        stats_data = data.get("stats", {})
        trace.stats = _stats_from_dict(stats_data)
        return trace


# ---------------------------------------------------------------------------
# Internal reconstruction helpers
# ---------------------------------------------------------------------------


def _feature_from_dict(data: dict[str, Any]) -> Feature:
    """Reconstruct a Feature from a dict."""
    feature = Feature(
        name=data.get("name", ""),
        status=data.get("status", "untested"),
        duration=data.get("duration", 0.0),
        description=data.get("description", ""),
        location=data.get("location", ""),
        tags=data.get("tags", []),
    )
    for s_data in data.get("scenarios", []):
        feature.scenarios.append(_scenario_from_dict(s_data))
    bg_data = data.get("background")
    if bg_data:
        feature.background = _background_from_dict(bg_data)
    return feature


def _scenario_from_dict(data: dict[str, Any]) -> Scenario:
    """Reconstruct a Scenario from a dict."""
    scenario = Scenario(
        name=data.get("name", ""),
        status=data.get("status", "untested"),
        duration=data.get("duration", 0.0),
        description=data.get("description", ""),
        location=data.get("location", ""),
        tags=data.get("tags", []),
        feature_name=data.get("feature_name", ""),
        rule_name=data.get("rule_name", ""),
        is_outline=data.get("is_outline", False),
        outline_name=data.get("outline_name", ""),
    )
    for step_data in data.get("steps", []):
        scenario.steps.append(_step_from_dict(step_data))
    bg_data = data.get("background")
    if bg_data:
        scenario.background = _background_from_dict(bg_data)
    return scenario


def _step_from_dict(data: dict[str, Any]) -> Step:
    """Reconstruct a Step from a dict."""
    step = Step(
        keyword=data.get("keyword", ""),
        name=data.get("name", ""),
        status=data.get("status", "untested"),
        duration=data.get("duration", 0.0),
        location=data.get("location", ""),
        text=data.get("text"),
        logs=data.get("logs", []),
    )
    for a_data in data.get("artifacts", []):
        step.artifacts.append(
            Artifact(
                type=a_data.get("type", "text"),
                name=a_data.get("name", ""),
                mime_type=a_data.get("mime_type", "application/octet-stream"),
                data_base64=a_data.get("data_base64", ""),
                text=a_data.get("text"),
            )
        )
    err_data = data.get("error")
    if err_data:
        step.error = ErrorInfo(
            message=err_data.get("message", ""),
            traceback=err_data.get("traceback", ""),
            exception_type=err_data.get("exception_type", ""),
        )
    table_data = data.get("table")
    if table_data:
        step.table = DataTable(
            headings=table_data.get("headings", []),
            rows=table_data.get("rows", []),
        )
    return step


def _background_from_dict(data: dict[str, Any]) -> Background:
    """Reconstruct a Background from a dict."""
    bg = Background(
        name=data.get("name", ""),
        keyword=data.get("keyword", "Background"),
        location=data.get("location", ""),
    )
    for step_data in data.get("steps", []):
        bg.steps.append(_step_from_dict(step_data))
    return bg


def _environment_from_dict(data: dict[str, Any]) -> Environment:
    """Reconstruct an Environment from a dict."""
    return Environment(
        python_version=data.get("python_version", ""),
        behave_version=data.get("behave_version", ""),
        behave_trace_version=data.get("behave_trace_version", ""),
        platform=data.get("platform", ""),
        hostname=data.get("hostname", ""),
        cwd=data.get("cwd", ""),
        command=data.get("command", ""),
        user=data.get("user", ""),
        cpu_count=data.get("cpu_count", 0),
        memory_mb=data.get("memory_mb", 0),
        git_branch=data.get("git_branch", ""),
        git_commit=data.get("git_commit", ""),
        git_remote=data.get("git_remote", ""),
        env_vars=data.get("env_vars", {}),
    )


def _stats_from_dict(data: dict[str, Any]) -> TraceStats:
    """Reconstruct TraceStats from a dict."""
    stats = TraceStats(
        total_features=data.get("total_features", 0),
        total_scenarios=data.get("total_scenarios", 0),
        total_steps=data.get("total_steps", 0),
        by_status=data.get("by_status", {}),
        duration=data.get("duration", 0.0),
        total_artifacts=data.get("total_artifacts", 0),
        total_screenshots=data.get("total_screenshots", 0),
        total_logs=data.get("total_logs", 0),
        slowest_step_duration=data.get("slowest_step_duration", 0.0),
        slowest_step_name=data.get("slowest_step_name", ""),
        avg_step_duration=data.get("avg_step_duration", 0.0),
    )
    start = data.get("start_time")
    if start:
        with contextlib.suppress(ValueError):
            stats.start_time = datetime.fromisoformat(start)
    end = data.get("end_time")
    if end:
        with contextlib.suppress(ValueError):
            stats.end_time = datetime.fromisoformat(end)
    return stats
