"""Utility helpers for behave-trace."""

from __future__ import annotations

import math


def safe_str(value: object) -> str:
    """Convert any value to string without raising exceptions.

    Falls back to ``repr()`` if ``str()`` fails.
    """
    try:
        return str(value)
    except Exception:
        try:
            return repr(value)
        except Exception:
            return "<unrepresentable>"


def safe_float(value: object, fallback: float = 0.0) -> float:
    """Convert any value to float without raising exceptions.

    Returns ``fallback`` if the value cannot be converted.
    """
    try:
        result = float(value)  # type: ignore[arg-type]
        if math.isnan(result) or math.isinf(result):
            return fallback
        return result
    except (TypeError, ValueError, OverflowError):
        return fallback


def format_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a human-readable string.

    Examples:
        ``0``      → ``"0ms"``
        ``0.234``  → ``"234ms"``
        ``1.23``   → ``"1.23s"``
        ``225``    → ``"3m 45s"``
        ``3725``   → ``"1h 2m 5s"``
    """
    if seconds is None or seconds <= 0 or math.isnan(seconds) or math.isinf(seconds):
        return "0ms"
    if seconds < 1:
        return f"{round(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"
