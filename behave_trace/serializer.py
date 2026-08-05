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
import math
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


def _sanitize_floats(obj: Any) -> Any:
    """Recursively replace NaN/Inf floats with 0.0.

    json.dumps with allow_nan=False raises ValueError for NaN/Inf.
    This walks the data tree and replaces them with 0.0, matching
    the behavior of safe_float in the collector.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _json_default(obj: Any) -> Any:
    """Fallback serializer for json.dumps.

    Falls back to ``str()`` for non-serializable types (e.g. datetime
    objects that slipped through as_dict).
    """
    return str(obj)


def _as_list(value: Any) -> list[Any]:
    """Return *value* if it is a list, otherwise an empty list."""
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    """Return *value* if it is a dict, otherwise an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> str:
    """Return *value* as a string, or empty string if None."""
    if value is None:
        return ""
    return str(value)


def _as_int(value: Any, fallback: int = 0) -> int:
    """Return *value* as an int, or *fallback* if conversion fails."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
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
        data = _sanitize_floats(as_dict(trace))
        p.write_text(
            json.dumps(data, indent=2, default=_json_default, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
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
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object at root, got {type(data).__name__}")
        return Serializer._from_dict(data)

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> Trace:
        """Reconstruct a Trace from a plain dict."""
        raw_version = data.get("version")
        trace = Trace(
            version=_as_str(raw_version) if raw_version is not None else "1",
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
        name=_as_str(data.get("name")),
        status=_as_str(data.get("status")) or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        description=_as_str(data.get("description")),
        location=_as_str(data.get("location")),
        tags=[str(t) for t in _as_list(data.get("tags"))],
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
        name=_as_str(data.get("name")),
        status=_as_str(data.get("status")) or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        description=_as_str(data.get("description")),
        location=_as_str(data.get("location")),
        tags=[str(t) for t in _as_list(data.get("tags"))],
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
            headings=[str(h) for h in _as_list(examples_data.get("headings"))],
            rows=[[str(c) for c in _as_list(row)] for row in _as_list(examples_data.get("rows"))],
        )
    return scenario


def _step_from_dict(data: dict[str, Any]) -> Step:
    """Reconstruct a Step from a dict."""
    raw_text = data.get("text")
    step = Step(
        keyword=_as_str(data.get("keyword")),
        name=_as_str(data.get("name")),
        status=_as_str(data.get("status")) or "untested",
        duration=safe_float(data.get("duration") or 0.0),
        location=_as_str(data.get("location")),
        text=str(raw_text) if raw_text is not None else None,
        logs=[
            item if isinstance(item, (str, dict)) else str(item)
            for item in _as_list(data.get("logs"))
        ],
    )
    for a_data in _as_list(data.get("artifacts")):
        if not isinstance(a_data, dict):
            continue
        art_text = a_data.get("text")
        step.artifacts.append(
            Artifact(
                type=_as_str(a_data.get("type")) or "text",
                name=_as_str(a_data.get("name")),
                mime_type=_as_str(a_data.get("mime_type")) or "application/octet-stream",
                data_base64=_as_str(a_data.get("data_base64")),
                text=str(art_text) if art_text is not None else None,
            )
        )
    err_data = data.get("error")
    if isinstance(err_data, dict):
        step.error = ErrorInfo(
            message=_as_str(err_data.get("message")),
            traceback=_as_str(err_data.get("traceback")),
            exception_type=_as_str(err_data.get("exception_type")),
        )
    table_data = data.get("table")
    if isinstance(table_data, dict):
        step.table = DataTable(
            headings=[str(h) for h in _as_list(table_data.get("headings"))],
            rows=[[str(c) for c in _as_list(row)] for row in _as_list(table_data.get("rows"))],
        )
    return step


def _background_from_dict(data: dict[str, Any]) -> Background:
    """Reconstruct a Background from a dict."""
    bg = Background(
        name=_as_str(data.get("name")),
        keyword=_as_str(data.get("keyword")) or "Background",
        location=_as_str(data.get("location")),
    )
    for step_data in _as_list(data.get("steps")):
        if not isinstance(step_data, dict):
            continue
        bg.steps.append(_step_from_dict(step_data))
    return bg


def _environment_from_dict(data: dict[str, Any]) -> Environment:
    """Reconstruct an Environment from a dict."""
    return Environment(
        python_version=_as_str(data.get("python_version")),
        behave_version=_as_str(data.get("behave_version")),
        behave_trace_version=_as_str(data.get("behave_trace_version")),
        platform=_as_str(data.get("platform")),
        hostname=_as_str(data.get("hostname")),
        cwd=_as_str(data.get("cwd")),
        command=_as_str(data.get("command")),
        user=_as_str(data.get("user")),
        cpu_count=_as_int(data.get("cpu_count")),
        memory_mb=_as_int(data.get("memory_mb")),
        git_branch=_as_str(data.get("git_branch")),
        git_commit=_as_str(data.get("git_commit")),
        git_remote=_as_str(data.get("git_remote")),
        env_vars={str(k): str(v) for k, v in _as_dict(data.get("env_vars")).items()},
    )


def _stats_from_dict(data: dict[str, Any]) -> TraceStats:
    """Reconstruct TraceStats from a dict."""
    stats = TraceStats(
        total_features=_as_int(data.get("total_features")),
        total_scenarios=_as_int(data.get("total_scenarios")),
        total_steps=_as_int(data.get("total_steps")),
        by_status={k: _as_int(v) for k, v in _as_dict(data.get("by_status")).items()},
        duration=safe_float(data.get("duration") or 0.0),
        total_artifacts=_as_int(data.get("total_artifacts")),
        total_screenshots=_as_int(data.get("total_screenshots")),
        total_logs=_as_int(data.get("total_logs")),
        slowest_step_duration=safe_float(data.get("slowest_step_duration") or 0.0),
        slowest_step_name=_as_str(data.get("slowest_step_name")),
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
