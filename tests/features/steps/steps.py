"""Simple step definitions for integration tests."""

from __future__ import annotations

import time

from behave import given, then, when  # type: ignore[import-not-found]


@given("a passing step")
def step_passing(context: object) -> None:
    time.sleep(0.01)


@when("I do something")
def step_do_something(context: object) -> None:
    time.sleep(0.01)


@then("I expect success")
def step_expect_success(context: object) -> None:
    assert True


@when("I do something that fails")
def step_do_something_fails(context: object) -> None:
    time.sleep(0.01)


@then("I expect failure")
def step_expect_failure(context: object) -> None:
    raise AssertionError("Intentional failure for integration test")
