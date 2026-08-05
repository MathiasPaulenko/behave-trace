"""Edge-case tests for the attach module."""

from __future__ import annotations

from unittest import mock

from behave_trace import attach


class _StubFormatter:
    """Minimal formatter stub that records attached artifacts."""

    def __init__(self) -> None:
        self.artifacts: list = []

    def attach(self, artifact: object) -> None:
        self.artifacts.append(artifact)

    def log(self, message: str, level: str = "info") -> None:
        pass


class _StubRunner:
    """Minimal runner stub."""

    def __init__(self, formatter: _StubFormatter | None = None) -> None:
        self.formatters = [formatter] if formatter else []


class _StubContext:
    """Minimal context stub."""

    def __init__(self, formatter: _StubFormatter | None = None) -> None:
        self._runner = _StubRunner(formatter)


class TestAttachScreenshotEdge:
    """Edge cases for attach_screenshot."""

    def test_screenshot_method_fails_then_get_screenshot_as_png_works(self) -> None:
        """When get_screenshot_as_png fails, fall back to screenshot()."""
        formatter = _StubFormatter()
        ctx = _StubContext(formatter)

        class Driver:
            def get_screenshot_as_png(self) -> bytes:
                raise RuntimeError("fail")

            def screenshot(self) -> bytes:
                return b"\x89PNG fake"

        attach.attach_screenshot(ctx, Driver(), name="fallback.png")
        assert len(formatter.artifacts) == 1
        assert formatter.artifacts[0].name == "fallback.png"

    def test_both_screenshot_methods_fail(self) -> None:
        """When both screenshot methods fail, no artifact is attached."""
        formatter = _StubFormatter()
        ctx = _StubContext(formatter)

        class Driver:
            def get_screenshot_as_png(self) -> bytes:
                raise RuntimeError("fail")

            def screenshot(self) -> bytes:
                raise RuntimeError("also fail")

        attach.attach_screenshot(ctx, Driver())
        assert len(formatter.artifacts) == 0


class TestAttachDomHeadVariants:
    """Tests for <base> tag injection with different HTML head formats."""

    def test_head_with_space_attribute(self) -> None:
        """Base tag injected when <head has attributes (space after head)."""
        formatter = _StubFormatter()
        ctx = _StubContext(formatter)

        html = '<html><head lang="en"><title>Test</title></head><body>Hello</body></html>'
        source = mock.Mock()
        source.current_url = "http://example.com"
        source.page_source = html

        attach.attach_dom(ctx, source)
        assert len(formatter.artifacts) == 1
        artifact = formatter.artifacts[0]
        assert "<base" in artifact.text
        assert '<head lang="en"><base href="http://example.com">' in artifact.text

    def test_no_head_tag_at_all(self) -> None:
        """Base tag prepended when no <head> tag exists."""
        formatter = _StubFormatter()
        ctx = _StubContext(formatter)

        html = "<div>No head here</div>"
        source = mock.Mock()
        source.current_url = "http://example.com"
        source.page_source = html

        attach.attach_dom(ctx, source)
        assert len(formatter.artifacts) == 1
        artifact = formatter.artifacts[0]
        assert artifact.text.startswith('<base href="http://example.com">')

    def test_content_method_fails(self) -> None:
        """When content() raises, no artifact is attached."""
        formatter = _StubFormatter()
        ctx = _StubContext(formatter)

        source = mock.Mock()
        source.current_url = None
        source.url = None
        source.page_source = None
        source.content = mock.Mock(side_effect=RuntimeError("fail"))

        attach.attach_dom(ctx, source)
        assert len(formatter.artifacts) == 0


class TestNormalizeNetworkDataEdge:
    """Edge cases for _normalize_network_data."""

    def test_bytes_input_valid_json(self) -> None:
        """Bytes input with valid JSON is parsed correctly."""
        data = b'{"method": "GET", "url": "http://example.com"}'
        result = attach._normalize_network_data(data)
        assert result is not None
        assert result["method"] == "GET"
        assert result["url"] == "http://example.com"

    def test_bytes_input_invalid_json(self) -> None:
        """Bytes input with invalid JSON returns None."""
        data = b"not json at all"
        result = attach._normalize_network_data(data)
        assert result is None

    def test_playwright_request_headers_exception(self) -> None:
        """When source.headers raises, headers defaults to empty dict."""
        source = mock.Mock()
        source.method = "POST"
        source.url = "http://example.com"
        source.headers = mock.Mock()
        type(source).headers = mock.PropertyMock(side_effect=RuntimeError("fail"))
        source.post_data = "data"
        # Ensure it's recognized as a Request (has method+url, no status)
        del source.status

        result = attach._normalize_network_data(source)
        assert result is not None
        assert result["headers"] == {}

    def test_playwright_response_headers_exception(self) -> None:
        """When response.headers raises, headers defaults to empty dict."""
        source = mock.Mock()
        source.status = 200
        source.url = "http://example.com"
        type(source).headers = mock.PropertyMock(side_effect=RuntimeError("fail"))
        source.text = mock.Mock(return_value="body")
        source.request = None

        result = attach._normalize_network_data(source)
        assert result is not None
        assert result["headers"] == {}

    def test_playwright_response_text_exception(self) -> None:
        """When response.text() raises, body defaults to None."""
        source = mock.Mock()
        source.status = 200
        source.url = "http://example.com"
        source.headers = {"X": "Y"}
        source.text = mock.Mock(side_effect=RuntimeError("fail"))
        source.request = None

        result = attach._normalize_network_data(source)
        assert result is not None
        assert result["body"] is None
