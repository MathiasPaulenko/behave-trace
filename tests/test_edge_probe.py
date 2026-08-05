"""Edge-case probe tests for deep audit.

These tests attempt to break public APIs with unusual inputs:
None, empty strings, unicode, emojis, negative values, etc.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from behave_trace.models import (
    Feature,
    Scenario,
    Step,
    Trace,
    normalize_level,
    normalize_status,
)
from behave_trace.serializer import Serializer, _sanitize_floats
from behave_trace.utils import format_duration, safe_float, safe_str


class TestSanitizeFloatsEdgeCases:
    """Deep edge-case testing for _sanitize_floats."""

    def test_empty_dict(self) -> None:
        assert _sanitize_floats({}) == {}

    def test_empty_list(self) -> None:
        assert _sanitize_floats([]) == []

    def test_empty_tuple(self) -> None:
        assert _sanitize_floats(()) == []

    def test_none_passthrough(self) -> None:
        assert _sanitize_floats(None) is None

    def test_string_passthrough(self) -> None:
        assert _sanitize_floats("hello") == "hello"

    def test_int_passthrough(self) -> None:
        assert _sanitize_floats(42) == 42

    def test_bool_passthrough(self) -> None:
        assert _sanitize_floats(True) is True

    def test_normal_float_passthrough(self) -> None:
        assert _sanitize_floats(3.14) == 3.14

    def test_negative_inf(self) -> None:
        assert _sanitize_floats(float("-inf")) == 0.0

    def test_nested_tuple_in_list(self) -> None:
        data = [1.0, (float("nan"),), {"a": (float("inf"),)}]
        result = _sanitize_floats(data)
        assert result == [1.0, [0.0], {"a": [0.0]}]

    def test_deeply_nested_structure(self) -> None:
        data = {"a": [{"b": [{"c": float("nan")}]}]}
        result = _sanitize_floats(data)
        assert result["a"][0]["b"][0]["c"] == 0.0

    def test_tuple_converted_to_list(self) -> None:
        result = _sanitize_floats((1.0, 2.0, 3.0))
        assert isinstance(result, list)
        assert result == [1.0, 2.0, 3.0]


class TestSerializerEdgeCases:
    """Deep edge-case testing for Serializer."""

    def test_load_empty_object(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text("{}")
        trace = Serializer.load(p)
        assert trace.features == []
        assert trace.version == "1"

    def test_load_array_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text("[]")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_null_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text("null")
        with pytest.raises(ValueError, match="Expected JSON object"):
            Serializer.load(p)

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text("{corrupted")
        with pytest.raises((json.JSONDecodeError, ValueError)):
            Serializer.load(p)

    def test_load_missing_version_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text(json.dumps({"features": [], "environment": {}, "stats": {}}))
        trace = Serializer.load(p)
        assert trace.version == "1"

    def test_load_extra_unknown_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text(
            json.dumps(
                {"version": "2", "features": [], "environment": {}, "stats": {}, "unknown": "x"}
            )
        )
        trace = Serializer.load(p)
        assert trace.version == "2"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "subdir" / "deep" / "trace.json"
        Serializer.save(Trace(), p)
        assert p.exists()

    def test_unicode_emoji_round_trip(self, tmp_path: Path) -> None:
        trace = Trace()
        f = Feature(name="Unicode: \u00e9\u00e8\u00ea \u65e5\u672c \U0001f600")
        s = Scenario(name="Emoji \U0001f600\U0001f601")
        step = Step(keyword="Given", name="Step \u00e9\u00e8\u00ea \U0001f600")
        s.steps.append(step)
        f.scenarios.append(s)
        trace.features.append(f)
        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        assert loaded.features[0].name == "Unicode: \u00e9\u00e8\u00ea \u65e5\u672c \U0001f600"
        assert loaded.features[0].scenarios[0].name == "Emoji \U0001f600\U0001f601"
        assert loaded.features[0].scenarios[0].steps[0].name == "Step \u00e9\u00e8\u00ea \U0001f600"

    def test_none_optional_fields_round_trip(self, tmp_path: Path) -> None:
        trace = Trace()
        f = Feature(name="test")
        s = Scenario(name="test")
        step = Step(keyword="Given", name="step", error=None, table=None)
        s.steps.append(step)
        f.scenarios.append(s)
        trace.features.append(f)
        p = tmp_path / "trace.json"
        Serializer.save(trace, p)
        loaded = Serializer.load(p)
        assert loaded.features[0].scenarios[0].steps[0].error is None
        assert loaded.features[0].scenarios[0].steps[0].table is None

    def test_empty_trace_round_trip(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        Serializer.save(Trace(), p)
        loaded = Serializer.load(p)
        assert loaded.features == []
        assert loaded.version == "1"
        assert loaded.environment.platform == ""

    def test_save_overwrites_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "trace.json"
        p.write_text("old content")
        Serializer.save(Trace(), p)
        loaded = Serializer.load(p)
        assert loaded.features == []

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        with pytest.raises((FileNotFoundError, OSError)):
            Serializer.load(p)


class TestNormalizeStatusEdgeCases:
    """Edge cases for normalize_status."""

    def test_none(self) -> None:
        assert normalize_status(None) == "untested"

    def test_uppercase(self) -> None:
        assert normalize_status("PASSED") == "passed"

    def test_whitespace(self) -> None:
        assert normalize_status("  failed  ") == "failed"

    def test_unknown_string(self) -> None:
        assert normalize_status("unknown") == "untested"

    def test_integer(self) -> None:
        assert normalize_status(42) == "untested"

    def test_object(self) -> None:
        assert normalize_status(object()) == "untested"

    def test_empty_string(self) -> None:
        assert normalize_status("") == "untested"

    def test_enum_like_with_name(self) -> None:
        class FakeStatus:
            name = "passed"

        assert normalize_status(FakeStatus()) == "passed"


class TestNormalizeLevelEdgeCases:
    """Edge cases for normalize_level."""

    def test_none(self) -> None:
        assert normalize_level(None) == "info"

    def test_empty_string(self) -> None:
        assert normalize_level("") == "info"

    def test_zero(self) -> None:
        assert normalize_level(0) == "info"

    def test_warn_alias(self) -> None:
        assert normalize_level("warn") == "warning"

    def test_err_alias(self) -> None:
        assert normalize_level("err") == "error"

    def test_fatal_alias(self) -> None:
        assert normalize_level("fatal") == "error"

    def test_critical_alias(self) -> None:
        assert normalize_level("critical") == "error"

    def test_unknown_defaults_to_info(self) -> None:
        assert normalize_level("unknown") == "info"

    def test_uppercase(self) -> None:
        assert normalize_level("ERROR") == "error"


class TestSafeFloatEdgeCases:
    """Edge cases for safe_float."""

    def test_none(self) -> None:
        assert safe_float(None) == 0.0

    def test_nan(self) -> None:
        assert safe_float(float("nan")) == 0.0

    def test_inf(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_negative_inf(self) -> None:
        assert safe_float(float("-inf")) == 0.0

    def test_int(self) -> None:
        assert safe_float(42) == 42.0

    def test_bool_true(self) -> None:
        assert safe_float(True) == 1.0

    def test_bool_false(self) -> None:
        assert safe_float(False) == 0.0

    def test_string_number(self) -> None:
        assert safe_float("3.14") == 3.14

    def test_invalid_string(self) -> None:
        assert safe_float("not a number") == 0.0

    def test_empty_list(self) -> None:
        assert safe_float([]) == 0.0

    def test_empty_dict(self) -> None:
        assert safe_float({}) == 0.0

    def test_negative(self) -> None:
        assert safe_float(-3.14) == -3.14


class TestFormatDurationEdgeCases:
    """Edge cases for format_duration."""

    def test_none(self) -> None:
        assert format_duration(None) == "0ms"

    def test_zero(self) -> None:
        assert format_duration(0) == "0ms"

    def test_negative(self) -> None:
        assert format_duration(-1) == "0ms"

    def test_nan(self) -> None:
        assert format_duration(float("nan")) == "0ms"

    def test_inf(self) -> None:
        assert format_duration(float("inf")) == "0ms"

    def test_milliseconds(self) -> None:
        assert format_duration(0.5) == "500ms"

    def test_seconds(self) -> None:
        assert format_duration(1.5) == "1.50s"

    def test_minutes(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_hours(self) -> None:
        assert format_duration(3600) == "1h 0m 0s"


class TestSafeStrEdgeCases:
    """Edge cases for safe_str."""

    def test_none(self) -> None:
        assert safe_str(None) == "None"

    def test_int(self) -> None:
        assert safe_str(42) == "42"

    def test_float(self) -> None:
        assert safe_str(3.14) == "3.14"

    def test_bool(self) -> None:
        assert safe_str(True) == "True"

    def test_list(self) -> None:
        assert safe_str([1, 2]) == "[1, 2]"

    def test_empty_string(self) -> None:
        assert safe_str("") == ""

    def test_unicode(self) -> None:
        assert safe_str("\u00e9\u00e8") == "\u00e9\u00e8"
