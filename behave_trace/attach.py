"""High-level attachment helpers for Behave environment.py hooks.

Usage in environment.py::

    from behave_trace import attach_screenshot, attach_dom, log

    def after_step(context, step):
        if step.status == "failed":
            attach_screenshot(context, driver, name="failure.png")
            attach_dom(context, driver, name="dom.html")
            log(f"URL at failure: {context.url}")
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .models import ARTIFACT_DOM, ARTIFACT_LOG, ARTIFACT_SCREENSHOT, Artifact


def _find_formatter(context: Any) -> Any:
    """Locate the TraceFormatter instance on the Behave context."""
    if context is None:
        return None
    runner = getattr(context, "_runner", None)
    if runner is None:
        return None
    formatters = getattr(runner, "formatters", None)
    if not formatters:
        return None
    for fmt in formatters:
        if hasattr(fmt, "attach") and hasattr(fmt, "log"):
            return fmt
    return None


def attach_screenshot(context: Any, source: Any, name: str = "screenshot.png") -> None:
    """Attach a screenshot to the current step.

    source can be: bytes, path string, Selenium WebDriver, Playwright Page.
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return

    data: bytes | None = None
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    elif isinstance(source, (str, Path)):
        try:
            data = Path(source).read_bytes()
        except Exception:
            return
    else:
        method = getattr(source, "get_screenshot_as_png", None)
        if callable(method):
            try:
                data = method()
            except Exception:
                return
        if data is None:
            method = getattr(source, "screenshot", None)
            if callable(method):
                try:
                    data = method()
                except Exception:
                    return

    if data is None:
        return

    formatter.attach(
        Artifact(
            type=ARTIFACT_SCREENSHOT,
            name=name,
            mime_type="image/png",
            data_base64=base64.b64encode(data).decode("ascii"),
        )
    )


def attach_dom(context: Any, source: Any, name: str = "dom.html") -> None:
    """Attach a DOM snapshot to the current step.

    source can be: HTML string, Selenium WebDriver, Playwright Page.
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return

    html: str | None = None
    if isinstance(source, str):
        html = source
    else:
        method = getattr(source, "page_source", None)
        if method:
            html = str(method)
        if html is None:
            method = getattr(source, "content", None)
            if callable(method):
                try:
                    html = method()
                except Exception:
                    return

    if html is None:
        return

    formatter.attach(
        Artifact(
            type=ARTIFACT_DOM,
            name=name,
            mime_type="text/html",
            text=html,
        )
    )


def attach_text(context: Any, text: str, name: str = "note.txt") -> None:
    """Attach a plain text snippet to the current step."""
    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.attach(
        Artifact(
            type=ARTIFACT_LOG,
            name=name,
            mime_type="text/plain",
            text=str(text),
        )
    )


def log(context: Any, message: str) -> None:
    """Append a log line to the current step."""
    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.log(str(message))
