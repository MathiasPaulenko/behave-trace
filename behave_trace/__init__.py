"""behave-trace — Trace viewer and step-by-step debugger for Behave BDD.

Two-phase model (like Playwright)::

    # 1. Capture
    behave --format behave-trace -o trace.json

    # 2. Visualize
    behave-trace show trace.json

Public API::

    from behave_trace import TraceFormatter, Trace
    from behave_trace import attach_screenshot, attach_dom, attach_text, attach_network, log
"""

from __future__ import annotations

from .attach import attach_dom, attach_network, attach_screenshot, attach_text, log
from .formatter import TraceFormatter
from .models import (
    ARTIFACT_DOM,
    ARTIFACT_LOG,
    ARTIFACT_NETWORK,
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    LOG_ERROR,
    LOG_INFO,
    LOG_WARNING,
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
)

__version__ = "1.0.0"

# Register formatter with Behave's internal registry (Behave 1.3.x doesn't
# auto-discover entry points — it uses a manual registry).
try:
    from behave.formatter._registry import register_as

    register_as("behave-trace", "behave_trace.formatter:TraceFormatter")
except Exception:
    pass

__all__ = [
    "ARTIFACT_DOM",
    "ARTIFACT_LOG",
    "ARTIFACT_NETWORK",
    "ARTIFACT_SCREENSHOT",
    "ARTIFACT_TEXT",
    "Artifact",
    "Background",
    "DataTable",
    "Environment",
    "ErrorInfo",
    "Feature",
    "LOG_ERROR",
    "LOG_INFO",
    "LOG_WARNING",
    "Scenario",
    "Step",
    "Trace",
    "TraceFormatter",
    "TraceStats",
    "attach_dom",
    "attach_network",
    "attach_screenshot",
    "attach_text",
    "log",
    "normalize_level",
]
