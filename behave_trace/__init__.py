"""behave-trace — Trace viewer and step-by-step debugger for Behave BDD.

Two-phase model (like Playwright)::

    # 1. Capture
    behave --format behave-trace -o trace.json

    # 2. Visualize
    behave-trace show trace.json

Public API::

    from behave_trace import TraceFormatter, Trace
    from behave_trace import attach_screenshot, attach_dom, log
"""

from __future__ import annotations

from .attach import attach_dom, attach_screenshot, attach_text, log
from .formatter import TraceFormatter
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
)

__version__ = "0.1.0"

# Register formatter with Behave's internal registry (Behave 1.3.x doesn't
# auto-discover entry points — it uses a manual registry).
try:
    from behave.formatter._registry import register_as

    register_as("behave-trace", "behave_trace.formatter:TraceFormatter")
except Exception:
    pass

__all__ = [
    "Artifact",
    "Background",
    "DataTable",
    "Environment",
    "ErrorInfo",
    "Feature",
    "Scenario",
    "Step",
    "Trace",
    "TraceFormatter",
    "TraceStats",
    "attach_dom",
    "attach_screenshot",
    "attach_text",
    "log",
]
