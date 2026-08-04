"""Tests for behave_trace.utils."""

from __future__ import annotations

from behave_trace.utils import format_duration, safe_float, safe_str

# ---------------------------------------------------------------------------
# safe_str
# ---------------------------------------------------------------------------


class TestSafeStr:
    def test_none(self) -> None:
        assert safe_str(None) == "None"

    def test_string(self) -> None:
        assert safe_str("hello") == "hello"

    def test_int(self) -> None:
        assert safe_str(42) == "42"

    def test_object_with_str(self) -> None:
        class Obj:
            def __str__(self) -> str:
                return "obj"

        assert safe_str(Obj()) == "obj"

    def test_object_that_raises_in_str(self) -> None:
        class BadStr:
            def __str__(self) -> str:
                raise RuntimeError("boom")

            def __repr__(self) -> str:
                return "BadStr()"

        assert safe_str(BadStr()) == "BadStr()"

    def test_object_that_raises_in_both(self) -> None:
        class BadBoth:
            def __str__(self) -> str:
                raise RuntimeError("str boom")

            def __repr__(self) -> str:
                raise RuntimeError("repr boom")

        result = safe_str(BadBoth())
        assert result == "<unrepresentable>"


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_none(self) -> None:
        assert format_duration(None) == "0ms"

    def test_zero(self) -> None:
        assert format_duration(0) == "0ms"

    def test_negative(self) -> None:
        assert format_duration(-5) == "0ms"

    def test_milliseconds(self) -> None:
        assert format_duration(0.234) == "234ms"

    def test_sub_millisecond(self) -> None:
        assert format_duration(0.001) == "1ms"

    def test_just_under_one_second(self) -> None:
        assert format_duration(0.999) == "999ms"

    def test_one_second(self) -> None:
        assert format_duration(1.0) == "1.00s"

    def test_seconds_with_decimals(self) -> None:
        assert format_duration(1.23) == "1.23s"

    def test_seconds_trailing_zeros(self) -> None:
        assert format_duration(45.7) == "45.70s"

    def test_just_under_one_minute(self) -> None:
        assert format_duration(59.99) == "59.99s"

    def test_one_minute(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(225) == "3m 45s"

    def test_just_under_one_hour(self) -> None:
        assert format_duration(3599) == "59m 59s"

    def test_one_hour(self) -> None:
        assert format_duration(3600) == "1h 0m 0s"

    def test_hours_minutes_seconds(self) -> None:
        assert format_duration(3725) == "1h 2m 5s"

    def test_large_value(self) -> None:
        assert format_duration(7384) == "2h 3m 4s"

    def test_nan(self) -> None:
        """Regression: NaN should not crash format_duration."""
        import math

        assert format_duration(math.nan) == "0ms"

    def test_positive_infinity(self) -> None:
        """Regression: infinity should not crash format_duration."""
        import math

        assert format_duration(math.inf) == "0ms"

    def test_negative_infinity(self) -> None:
        """Regression: negative infinity should not crash format_duration."""
        import math

        assert format_duration(-math.inf) == "0ms"


# ---------------------------------------------------------------------------
# safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    def test_int(self) -> None:
        assert safe_float(42) == 42.0

    def test_float(self) -> None:
        assert safe_float(3.14) == 3.14

    def test_string_number(self) -> None:
        assert safe_float("2.5") == 2.5

    def test_none(self) -> None:
        assert safe_float(None) == 0.0

    def test_empty_string(self) -> None:
        assert safe_float("") == 0.0

    def test_non_numeric_string(self) -> None:
        """Regression: non-numeric string should return fallback, not crash."""
        assert safe_float("N/A") == 0.0

    def test_list(self) -> None:
        """Regression: non-numeric type should return fallback, not crash."""
        assert safe_float([1, 2, 3]) == 0.0

    def test_dict(self) -> None:
        assert safe_float({"a": 1}) == 0.0

    def test_nan(self) -> None:
        """Regression: NaN should return fallback."""
        import math

        assert safe_float(math.nan) == 0.0

    def test_inf(self) -> None:
        """Regression: infinity should return fallback."""
        import math

        assert safe_float(math.inf) == 0.0

    def test_negative_inf(self) -> None:
        import math

        assert safe_float(-math.inf) == 0.0

    def test_custom_fallback(self) -> None:
        assert safe_float("bad", fallback=-1.0) == -1.0

    def test_bool_true(self) -> None:
        assert safe_float(True) == 1.0

    def test_bool_false(self) -> None:
        assert safe_float(False) == 0.0
