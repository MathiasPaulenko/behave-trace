"""Tests for behave_trace.attach."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from behave_trace.attach import (
    _find_formatter,
    attach_dom,
    attach_screenshot,
    attach_text,
    log,
)
from behave_trace.models import (
    ARTIFACT_DOM,
    ARTIFACT_LOG,
    ARTIFACT_SCREENSHOT,
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
        self.logged: list[str] = []

    def attach(self, artifact: Artifact) -> None:
        self.attached.append(artifact)

    def log(self, message: str) -> None:
        self.logged.append(message)


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
        assert a.type == ARTIFACT_LOG
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
        assert fmt.logged == ["something happened"]

    def test_non_string_message(self) -> None:
        fmt = FakeFormatter()
        ctx = make_context(fmt)
        log(ctx, 123)
        assert fmt.logged == ["123"]

    def test_no_formatter_is_noop(self) -> None:
        ctx = make_context(None)
        log(ctx, "test")
        # Should not raise

    def test_none_context_is_noop(self) -> None:
        log(None, "test")
        # Should not raise
