"""Step definitions for the calculator example.

Demonstrates behave-trace attachments: screenshots, DOM snapshots, and logs.
"""

from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when  # type: ignore[import-not-found]

# Ensure the example package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calculator import Calculator  # noqa: E402

from behave_trace import attach_dom, attach_screenshot, log  # noqa: E402


@given("a calculator")
def step_given_calculator(context):
    context.calc = Calculator()
    log(context, "Calculator initialized")


@given("I enter {number:g} into the calculator")
def step_enter_number(context, number):
    context.calc.enter(number)
    log(context, f"Entered {number}")


@when("I press add")
def step_press_add(context):
    context.result = context.calc.add()
    attach_screenshot(context, context.calc.screenshot(), name="after_add.png")
    attach_dom(context, context.calc.render(), name="display.html")


@when("I press subtract")
def step_press_subtract(context):
    context.result = context.calc.subtract()
    attach_screenshot(context, context.calc.screenshot(), name="after_subtract.png")
    attach_dom(context, context.calc.render(), name="display.html")


@when("I press multiply")
def step_press_multiply(context):
    context.result = context.calc.multiply()
    attach_screenshot(context, context.calc.screenshot(), name="after_multiply.png")
    attach_dom(context, context.calc.render(), name="display.html")


@when("I press divide")
def step_press_divide(context):
    try:
        context.result = context.calc.divide()
        attach_screenshot(context, context.calc.screenshot(), name="after_divide.png")
        attach_dom(context, context.calc.render(), name="display.html")
    except ZeroDivisionError:
        attach_screenshot(context, context.calc.screenshot(), name="error_divide.png")
        attach_dom(context, context.calc.render(), name="error_display.html")
        log(context, f"Division error: {context.calc.error}")
        context.result = None


@then("the result should be {expected:g}")
def step_result_should_be(context, expected):
    assert context.result == expected, f"Expected {expected}, got {context.result}"
    log(context, f"Result verified: {context.result}")


@then("the calculator should show an error")
def step_should_show_error(context):
    assert context.calc.error is not None, "Expected an error but got none"
    assert context.result is None, "Expected result to be None on error"
    log(context, f"Error verified: {context.calc.error}")
