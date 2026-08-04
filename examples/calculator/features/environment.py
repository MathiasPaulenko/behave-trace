"""Environment hooks for the calculator example.

Demonstrates behave-trace attachment helpers in after_step.
"""

from __future__ import annotations

from behave_trace import log


def before_scenario(context, scenario):
    """Initialize context for each scenario."""
    context.calc = None
    context.result = None


def after_step(context, step):
    """Log step completion after every step."""
    log(context, f"Step completed: {step.name}")
