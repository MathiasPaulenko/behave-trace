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
from .utils import safe_float


def _as_list(value: Any) -> list[Any]:
    """Return *value* if it is a list, otherwise an empty list."""
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    """Return *value* if it is a dict, otherwise an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> str:
    """Return *value* as a string, or empty string if falsy."""
    return str(value) if value else ""


def _as_int(value: Any, fallback: int = 0) -> int:
    """Return *value* as an int, or *fallback* if conversion fails."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


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
            ValueError: If the JSON root is not a JSON object.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Trace file not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object at root, got {type(data).__name__}")
        return Serializer._from_dict(data)

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> Trace:
        """Reconstruct a Trace from a plain dict."""
        trace = Trace(
            version=data.get("version") or "1",
            features=[],
        )
        created = data.get("created_at")
        if isinstance(created, str):
            with contextlib.suppress(ValueError):
                trace.created_at = datetime.fromisoformat(created)
        for f_data in _as_list(data.get("features")):
            if not isinstance(f_data, dict):
                continue
            feature = _feature_from_dict(f_data)
            trace.features.append(feature)
        env_data = _as_dict(data.get("environment"))
        trace.environment = _environment_from_dict(env_data)
        stats_data = _as_dict(data.get("stats"))
        trace.stats = _stats_from_dict(stats_data)
        return trace


# ---------------------------------------------------------------------------
# Internal reconstruction helpers
# ---------------------------------------------------------------------------


def _feature_from_dict(data: dict[str, Any]) -> Feature:
    """Reconstruct a Feature from a dict."""
    feature = Feature(
        name=data.get("name") or "",
        status=data.get("status") or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        description=data.get("description") or "",
        location=data.get("location") or "",
        tags=_as_list(data.get("tags")),
    )
    for s_data in _as_list(data.get("scenarios")):
        if not isinstance(s_data, dict):
            continue
        feature.scenarios.append(_scenario_from_dict(s_data))
    bg_data = data.get("background")
    if isinstance(bg_data, dict):
        feature.background = _background_from_dict(bg_data)
    return feature


def _scenario_from_dict(data: dict[str, Any]) -> Scenario:
    """Reconstruct a Scenario from a dict."""
    scenario = Scenario(
        name=data.get("name") or "",
        status=data.get("status") or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        description=data.get("description") or "",
        location=data.get("location") or "",
        tags=_as_list(data.get("tags")),
        feature_name=_as_str(data.get("feature_name")),
        rule_name=_as_str(data.get("rule_name")),
        is_outline=bool(data.get("is_outline")),
        outline_name=_as_str(data.get("outline_name")),
    )
    for step_data in _as_list(data.get("steps")):
        if not isinstance(step_data, dict):
            continue
        scenario.steps.append(_step_from_dict(step_data))
    bg_data = data.get("background")
    if isinstance(bg_data, dict):
        scenario.background = _background_from_dict(bg_data)
    examples_data = data.get("examples")
    if isinstance(examples_data, dict):
        scenario.examples = DataTable(
            headings=_as_list(examples_data.get("headings")),
            rows=_as_list(examples_data.get("rows")),
        )
    return scenario


def _step_from_dict(data: dict[str, Any]) -> Step:
    """Reconstruct a Step from a dict."""
    step = Step(
        keyword=data.get("keyword") or "",
        name=data.get("name") or "",
        status=data.get("status") or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        location=data.get("location") or "",
        text=data.get("text"),
        logs=_as_list(data.get("logs")),
    )
    for a_data in _as_list(data.get("artifacts")):
        if not isinstance(a_data, dict):
            continue
        step.artifacts.append(
            Artifact(
                type=a_data.get("type") or "text",
                name=a_data.get("name") or "",
                mime_type=a_data.get("mime_type") or "application/octet-stream",
                data_base64=a_data.get("data_base64") or "",
                text=a_data.get("text"),
            )
        )
    err_data = data.get("error")
    if isinstance(err_data, dict):
        step.error = ErrorInfo(
            message=err_data.get("message") or "",
            traceback=err_data.get("traceback") or "",
            exception_type=err_data.get("exception_type") or "",
        )
    table_data = data.get("table")
    if isinstance(table_data, dict):
        step.table = DataTable(
            headings=_as_list(table_data.get("headings")),
            rows=_as_list(table_data.get("rows")),
        )
    return step


def _background_from_dict(data: dict[str, Any]) -> Background:
    """Reconstruct a Background from a dict."""
    bg = Background(
        name=data.get("name") or "",
        keyword=data.get("keyword") or "Background",
        location=data.get("location") or "",
    )
    for step_data in _as_list(data.get("steps")):
        if not isinstance(step_data, dict):
            continue
        bg.steps.append(_step_from_dict(step_data))
    return bg


def _environment_from_dict(data: dict[str, Any]) -> Environment:
    """Reconstruct an Environment from a dict."""
    return Environment(
        python_version=data.get("python_version") or "",
        behave_version=data.get("behave_version") or "",
        behave_trace_version=data.get("behave_trace_version") or "",
        platform=data.get("platform") or "",
        hostname=data.get("hostname") or "",
        cwd=data.get("cwd") or "",
        command=data.get("command") or "",
        user=data.get("user") or "",
        cpu_count=_as_int(data.get("cpu_count")),
        memory_mb=_as_int(data.get("memory_mb")),
        git_branch=data.get("git_branch") or "",
        git_commit=data.get("git_commit") or "",
        git_remote=data.get("git_remote") or "",
        env_vars=_as_dict(data.get("env_vars")),
    )


def _stats_from_dict(data: dict[str, Any]) -> TraceStats:
    """Reconstruct TraceStats from a dict."""
    stats = TraceStats(
        total_features=_as_int(data.get("total_features")),
        total_scenarios=_as_int(data.get("total_scenarios")),
        total_steps=_as_int(data.get("total_steps")),
        by_status=_as_dict(data.get("by_status")),
        duration=safe_float(data.get("duration") or 0.0),
        total_artifacts=_as_int(data.get("total_artifacts")),
        total_screenshots=_as_int(data.get("total_screenshots")),
        total_logs=_as_int(data.get("total_logs")),
        slowest_step_duration=safe_float(data.get("slowest_step_duration") or 0.0),
        slowest_step_name=data.get("slowest_step_name") or "",
        avg_step_duration=safe_float(data.get("avg_step_duration") or 0.0),
    )
    start = data.get("start_time")
    if isinstance(start, str):
        with contextlib.suppress(ValueError):
            stats.start_time = datetime.fromisoformat(start)
    end = data.get("end_time")
    if isinstance(end, str):
        with contextlib.suppress(ValueError):
            stats.end_time = datetime.fromisoformat(end)
    return stats
