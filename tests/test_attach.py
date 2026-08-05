"""Tests for behave_trace.attach."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from behave_trace.attach import (
    _find_formatter,
    attach_dom,
    attach_network,
    attach_screenshot,
    attach_text,
    log,
)
from behave_trace.models import (
    ARTIFACT_DOM,
    ARTIFACT_NETWORK,
    ARTIFACT_SCREENSHOT,
    ARTIFACT_TEXT,
    Artifact,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class StubRunner:
    formatters: list[Any] = field(default_factory=list)


@dataclass
class StubContext:
    _runner: Any = None


class FakeFormatter:
    """Minimal formatter mock that records attach/log calls."""

    def __init__(self) -> None:
        self.attached: list[Artifact] = []
        self.logged: list[tuple[str, str]] = []

    def attach(self, artifact: Artifact) -> None:
        self.attached.append(artifact)

    def log(self, message: str, level: str = "info") -> None:
        self.logged.append((message, level))


@dataclass
class StubSeleniumDriver:
    page_source: str = "<html>Selenium</html>"

    def get_screenshot_as_png(self) -> bytes:
        return b"\x89PNG fake screenshot"


class StubPlaywrightPage:
    def screenshot(self) -> bytes:
        return b"\x89PNG playwright screenshot"

    def content(self) -> str:
        return "<html>Playwright</html>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_context(formatter: Any = None) -> StubContext:
    if formatter is None:
        return StubContext(_runner=StubRunner(formatters=[]))
    return StubContext(_runner=StubRunner(formatters=[formatter]))


# ---------------------------------------------------------------------------
# _find_formatter
# ---------------------------------------------------------------------------


class TestFindFormatter:
    def test_finds_formatter(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        assert _find_formatter(ctx) is fmt

    def test_no_formatter_returns_none(self) -> None:
        ctx = make_context(None)
        assert _find_formatter(ctx) is None

    def test_none_context_returns_none(self) -> None:
        assert _find_formatter(None) is None

    def test_no_runner_returns_none(self) -> None:
        ctx = StubContext(_runner=None)
        assert _find_formatter(ctx) is None

    def test_skips_non_trace_formatters(self) -> None:
        @dataclass
        class OtherFormatter:
            name: str = "plain"

        ctx = StubContext(_runner=StubRunner(formatters=[OtherFormatter()]))
        assert _find_formatter(ctx) is None

    def test_finds_among_multiple(self) -> None:
        @dataclass
        class OtherFormatter:
            name: str = "plain"

        fmt = FakeFormatter()
        ctx = StubContext(_runner=StubRunner(formatters=[OtherFormatter(), fmt]))
        assert _find_formatter(ctx) is fmt


# ---------------------------------------------------------------------------
# attach_screenshot
# ---------------------------------------------------------------------------


class TestAttachScreenshot:
    def test_with_bytes(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, b"\x89PNG data", name="shot.png")
        assert len(fmt.attached) == 1
        a = fmt.attached[0]
        assert a.type == ARTIFACT_SCREENSHOT
        assert a.name == "shot.png"
        assert a.mime_type == "image/png"
        assert a.data_base64 != ""

    def test_with_path(self, tmp_path: Path) -> None:
        img = tmp_path / "screenshot.png"
        img.write_bytes(b"\x89PNG from file")
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, str(img))
        assert len(fmt.attached) == 1
        assert fmt.attached[0].type == ARTIFACT_SCREENSHOT

    def test_with_pathlib_path(self, tmp_path: Path) -> None:
        img = tmp_path / "screenshot.png"
        img.write_bytes(b"\x89PNG from pathlib")
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, img)
        assert len(fmt.attached) == 1

    def test_with_selenium_driver(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, StubSeleniumDriver())
        assert len(fmt.attached) == 1
        assert fmt.attached[0].type == ARTIFACT_SCREENSHOT

    def test_with_playwright_page(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, StubPlaywrightPage())
        assert len(fmt.attached) == 1
        assert fmt.attached[0].type == ARTIFACT_SCREENSHOT

    def test_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        # Should not raise
        attach_screenshot(ctx, b"data")

    def test_none_context_is_noop(self) -> None:
        attach_screenshot(None, b"data")
        # Should not raise

    def test_unreadable_path_is_noop(self, tmp_path: Path) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, str(tmp_path / "nonexistent.png"))
        assert len(fmt.attached) == 0

    def test_base64_encodes_correctly(self) -> None:
        import base64

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        raw = b"hello world"
        attach_screenshot(ctx, raw)
        a = fmt.attached[0]
        assert base64.b64decode(a.data_base64) == raw

    def test_falls_back_to_screenshot_when_get_screenshot_as_png_fails(self) -> None:
        """Regression: get_screenshot_as_png raising should not prevent screenshot() fallback."""

        class FailingDriver:
            def get_screenshot_as_png(self) -> bytes:
                raise RuntimeError("selenium not ready")

            def screenshot(self) -> bytes:
                return b"\x89PNG fallback"

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_screenshot(ctx, FailingDriver())
        assert len(fmt.attached) == 1
        import base64

        assert base64.b64decode(fmt.attached[0].data_base64) == b"\x89PNG fallback"


# ---------------------------------------------------------------------------
# attach_dom
# ---------------------------------------------------------------------------


class TestAttachDom:
    def test_with_html_string(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, "<html><body>test</body></html>", name="dom.html")
        assert len(fmt.attached) == 1
        a = fmt.attached[0]
        assert a.type == ARTIFACT_DOM
        assert a.name == "dom.html"
        assert a.mime_type == "text/html"
        assert a.text == "<html><body>test</body></html>"

    def test_with_selenium_driver(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, StubSeleniumDriver())
        assert len(fmt.attached) == 1
        assert fmt.attached[0].text == "<html>Selenium</html>"

    def test_with_playwright_page(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, StubPlaywrightPage())
        assert len(fmt.attached) == 1
        assert fmt.attached[0].text == "<html>Playwright</html>"

    def test_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        attach_dom(ctx, "<html></html>")
        # Should not raise

    def test_none_context_is_noop(self) -> None:
        attach_dom(None, "<html></html>")
        # Should not raise

    def test_empty_page_source_is_attached(self) -> None:
        """Regression: empty page_source string was treated as falsy and skipped."""
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, StubSeleniumDriver(page_source=""), name="empty.html")
        assert len(fmt.attached) == 1
        assert fmt.attached[0].text == ""

    def test_empty_string_html_is_attached(self) -> None:
        """Regression: empty string source should be attached, not skipped."""
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, "", name="empty.html")
        assert len(fmt.attached) == 1
        assert fmt.attached[0].text == ""

    def test_page_source_property_raising_non_attribute_error(self) -> None:
        """Regression: getattr(page_source) can raise non-AttributeError exceptions.

        Selenium's page_source property can raise WebDriverException when the
        browser is unavailable.  getattr with a default only catches
        AttributeError, so the exception would propagate and crash attach_dom.
        """

        class FailingDriver:
            @property
            def page_source(self) -> str:
                raise RuntimeError("browser not available")

            def content(self) -> str:
                return "<html>fallback</html>"

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, FailingDriver())
        assert len(fmt.attached) == 1
        assert fmt.attached[0].text == "<html>fallback</html>"

    def test_page_source_raising_and_content_also_failing(self) -> None:
        """Regression: both page_source and content failing should not crash."""

        class TotallyFailingDriver:
            @property
            def page_source(self) -> str:
                raise RuntimeError("browser not available")

            def content(self) -> str:
                raise RuntimeError("content also fails")

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, TotallyFailingDriver())
        assert len(fmt.attached) == 0


# ---------------------------------------------------------------------------
# attach_text
# ---------------------------------------------------------------------------


class TestAttachText:
    def test_attaches_text(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_text(ctx, "some note", name="note.txt")
        assert len(fmt.attached) == 1
        a = fmt.attached[0]
        assert a.type == ARTIFACT_TEXT
        assert a.name == "note.txt"
        assert a.mime_type == "text/plain"
        assert a.text == "some note"

    def test_non_string_text(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_text(ctx, 42)
        assert fmt.attached[0].text == "42"

    def test_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        attach_text(ctx, "note")
        # Should not raise

    def test_none_context_is_noop(self) -> None:
        attach_text(None, "note")
        # Should not raise


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


class TestLog:
    def test_logs_message(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        log(ctx, "something happened")
        assert fmt.logged == [("something happened", "info")]

    def test_logs_with_level(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        log(ctx, "something broke", level="error")
        assert fmt.logged == [("something broke", "error")]

    def test_non_string_message(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        log(ctx, 123)
        assert fmt.logged == [("123", "info")]

    def test_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        log(ctx, "test")
        # Should not raise

    def test_none_context_is_noop(self) -> None:
        log(None, "test")
        # Should not raise


# ---------------------------------------------------------------------------
# attach_network tests
# ---------------------------------------------------------------------------


class TestAttachNetwork:
    def test_attach_network_with_dict(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_network(
            ctx,
            {
                "method": "GET",
                "url": "http://api.example.com/users",
                "status": 200,
                "headers": {"Accept": "application/json"},
                "body": None,
                "response": {"status": 200, "body": "[]"},
            },
        )
        assert len(fmt.attached) == 1
        art = fmt.attached[0]
        assert art.type == ARTIFACT_NETWORK
        assert art.mime_type == "application/json"
        import json

        payload = json.loads(art.text)
        assert payload["method"] == "GET"
        assert payload["url"] == "http://api.example.com/users"
        assert payload["status"] == 200

    def test_attach_network_with_minimal_dict(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_network(ctx, {"method": "POST", "url": "http://example.com"})
        assert len(fmt.attached) == 1
        art = fmt.attached[0]
        assert art.type == ARTIFACT_NETWORK
        import json

        payload = json.loads(art.text)
        assert payload["method"] == "POST"
        assert payload["url"] == "http://example.com"
        assert payload["status"] is None

    def test_attach_network_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        attach_network(ctx, {"method": "GET", "url": "http://example.com"})
        # Should not raise

    def test_attach_network_none_context_is_noop(self) -> None:
        attach_network(None, {"method": "GET", "url": "http://example.com"})
        # Should not raise

    def test_attach_network_with_playwright_request(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)

        class MockRequest:
            method = "GET"
            url = "http://example.com/api"
            headers = {"Content-Type": "application/json"}
            post_data = '{"query": "users"}'

        attach_network(ctx, MockRequest())
        assert len(fmt.attached) == 1
        import json

        payload = json.loads(fmt.attached[0].text)
        assert payload["method"] == "GET"
        assert payload["url"] == "http://example.com/api"
        assert payload["status"] is None
        assert payload["body"] == '{"query": "users"}'

    def test_attach_network_with_playwright_response(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)

        class MockRequest:
            method = "POST"

        class MockResponse:
            status = 201
            url = "http://example.com/api/create"
            headers = {"Content-Type": "application/json"}
            request = MockRequest()

            def text(self) -> str:
                return '{"id": 1}'

        attach_network(ctx, MockResponse())
        assert len(fmt.attached) == 1
        import json

        payload = json.loads(fmt.attached[0].text)
        assert payload["status"] == 201
        assert payload["url"] == "http://example.com/api/create"
        assert payload["response"]["body"] == '{"id": 1}'

    def test_attach_network_with_json_string(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_network(ctx, '{"method": "DELETE", "url": "http://example.com/1", "status": 204}')
        assert len(fmt.attached) == 1
        import json

        payload = json.loads(fmt.attached[0].text)
        assert payload["method"] == "DELETE"
        assert payload["status"] == 204

    def test_attach_network_with_invalid_string_is_noop(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_network(ctx, "not json at all")
        assert len(fmt.attached) == 0

    def test_attach_network_with_unrecognized_object_is_noop(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_network(ctx, 42)
        assert len(fmt.attached) == 0


class TestAttachDomBaseUrlEscaping:
    """Regression tests for HTML injection via ``base_url``.

    ``base_url`` is extracted from the source object's ``current_url`` or
    ``url`` attribute.  If it contains special characters, it was injected
    raw into ``<base href="...">``, allowing HTML injection.

    Additionally, the local variable ``html`` (the DOM string) shadowed
    the imported ``html`` module, so ``html.escape()`` raised
    ``AttributeError`` instead of escaping.
    """

    def test_base_url_with_quote_is_escaped(self) -> None:
        """Regression: ``base_url`` containing ``"`` was injected raw into
        ``<base href="...">``, allowing attribute breakout.
        """

        class MaliciousDriver:
            current_url = 'http://evil.com" onload="alert(1)'

            @property
            def page_source(self) -> str:
                return "<html><head></head><body>test</body></html>"

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, MaliciousDriver(), name="dom.html")
        assert len(fmt.attached) == 1
        text = fmt.attached[0].text
        # The quote must be escaped, not raw
        assert 'onload="alert(1)' not in text
        assert "&quot;" in text

    def test_base_url_with_angle_brackets_is_escaped(self) -> None:
        """Regression: ``base_url`` containing ``<`` or ``>`` could inject
        arbitrary HTML tags into the ``<base>`` tag.
        """

        class MaliciousDriver:
            current_url = 'http://evil.com"><script>alert(1)</script><x href="'

            @property
            def page_source(self) -> str:
                return "<html><head></head><body>test</body></html>"

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        attach_dom(ctx, MaliciousDriver(), name="dom.html")
        assert len(fmt.attached) == 1
        text = fmt.attached[0].text
        assert "<script>alert(1)</script>" not in text

    def test_html_module_shadowing_does_not_crash(self) -> None:
        """Regression: the local variable ``html`` (DOM string) shadowed
        the imported ``html`` module, so ``html.escape()`` raised
        ``AttributeError: 'str' object has no attribute 'escape'``.
        """

        class DriverWithUrl:
            current_url = "http://example.com/page"

            @property
            def page_source(self) -> str:
                return "<html><head></head><body>test</body></html>"

        fmt = FakeFormatter()
        ctx = make_context(fmt)
        # This should not raise AttributeError
        attach_dom(ctx, DriverWithUrl(), name="dom.html")
        assert len(fmt.attached) == 1
        assert "<base " in fmt.attached[0].text
