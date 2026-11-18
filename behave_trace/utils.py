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
    try:
        value = float(seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return "0ms"
    if value <= 0 or math.isnan(value) or math.isinf(value):
        return "0ms"
    seconds = value
    ms = round(seconds * 1000)
    if ms < 1000:
        return f"{ms}ms"
    if seconds < 59.995:  # below this it can't round up to "60.00s"
        return f"{seconds:.2f}s"
    # Rounded whole seconds keep rollover boundaries clean
    # (59.999s → "1m 0s", 3599.9s → "1h 0m 0s").
    total = int(round(seconds))
    if total < 3600:
        m, s = divmod(total, 60)
        return f"{m}m {s}s"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"
