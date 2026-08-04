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
import contextlib
from pathlib import Path
from typing import Any

from .models import ARTIFACT_DOM, ARTIFACT_NETWORK, ARTIFACT_SCREENSHOT, ARTIFACT_TEXT, Artifact


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
            with contextlib.suppress(Exception):
                data = method()
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

    When source is a WebDriver or Page, the current URL is extracted and
    injected as a ``<base>`` tag so relative URLs (CSS, JS, images) resolve
    correctly in the viewer's iframe.
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return

    html: str | None = None
    base_url: str | None = None

    if isinstance(source, str):
        html = source
    else:
        # Try to get current URL for <base> tag injection
        current_url = getattr(source, "current_url", None)
        if current_url is None:
            current_url = getattr(source, "url", None)
        if isinstance(current_url, str):
            base_url = current_url

        try:
            page_source = getattr(source, "page_source", None)
        except Exception:
            page_source = None
        if page_source is not None:
            html = str(page_source)
        if html is None:
            method = getattr(source, "content", None)
            if callable(method):
                try:
                    html = method()
                except Exception:
                    return

    if html is None:
        return

    # Inject <base> tag so relative URLs resolve in the viewer's iframe
    if base_url and "<base " not in html:
        base_tag = f'<base href="{base_url}">'
        if "<head>" in html:
            html = html.replace("<head>", f"<head>{base_tag}", 1)
        elif "<head " in html:
            html = html.replace("<head ", f"<head>{base_tag} ", 1)
        else:
            html = base_tag + html

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
            type=ARTIFACT_TEXT,
            name=name,
            mime_type="text/plain",
            text=str(text),
        )
    )


def log(context: Any, message: str, level: str = "info") -> None:
    """Append a log line to the current step.

    Args:
        context: The Behave context object.
        message: The log message text.
        level: Log level — "info", "warning", or "error" (default: "info").
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.log(str(message), level=level)


def attach_network(context: Any, request_data: Any, name: str = "network") -> None:
    """Attach an HTTP request/response as a network artifact to the current step.

    Args:
        context: The Behave context object.
        request_data: Can be:
            - A dict with keys: ``method``, ``url``, ``status``, ``headers``,
              ``body``, ``response``.
            - A Selenium request/response log entry (from ``driver.get_log``).
            - A Playwright :class:`Request` or :class:`Response` object.
        name: Artifact name (default: "network").
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return

    payload = _normalize_network_data(request_data)
    if payload is None:
        return

    import json as _json

    formatter.attach(
        Artifact(
            type=ARTIFACT_NETWORK,
            name=name,
            mime_type="application/json",
            text=_json.dumps(payload, default=str),
        )
    )


def _normalize_network_data(source: Any) -> dict[str, Any] | None:
    """Normalize various network data sources into a common dict format.

    Returns a dict with keys: method, url, status, headers, body, response.
    Returns None if the source cannot be recognized.
    """
    if isinstance(source, dict):
        return {
            "method": source.get("method", ""),
            "url": source.get("url", ""),
            "status": source.get("status"),
            "headers": source.get("headers", {}),
            "body": source.get("body"),
            "response": source.get("response"),
        }

    # Playwright Request object
    if hasattr(source, "method") and hasattr(source, "url") and not hasattr(source, "status"):
        try:
            headers = dict(source.headers) if source.headers else {}
        except Exception:
            headers = {}
        try:
            post_data = source.post_data
        except Exception:
            post_data = None
        return {
            "method": source.method,
            "url": source.url,
            "status": None,
            "headers": headers,
            "body": post_data,
            "response": None,
        }

    # Playwright Response object
    if hasattr(source, "status") and hasattr(source, "url"):
        try:
            headers = dict(source.headers) if source.headers else {}
        except Exception:
            headers = {}
        try:
            body = source.text()
        except Exception:
            body = None
        _req = getattr(source, "request", None)
        method = _req.method if _req is not None and hasattr(_req, "method") else ""
        return {
            "method": method,
            "url": source.url,
            "status": source.status,
            "headers": headers,
            "body": None,
            "response": {"status": source.status, "body": body, "headers": headers},
        }

    # Selenium performance log entry
    if isinstance(source, (str, bytes)):
        import json as _json

        try:
            if isinstance(source, str):
                entry = _json.loads(source)
            else:
                entry = _json.loads(source.decode("utf-8"))
        except Exception:
            return None
        return _normalize_network_data(entry)

    return None
