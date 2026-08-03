"""E2E step definitions for behave-trace meta-tests.

These steps run Behave with the behave-trace formatter on inner test
features and verify the resulting trace JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from behave import given, then, when  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FORMATTER = "behave_trace.formatter:TraceFormatter"


def _run_behave(inner_features: Path, trace_path: Path) -> subprocess.CompletedProcess[str]:
    """Run behave with behave-trace formatter on inner features."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "behave",
            "--format",
            _FORMATTER,
            "-o",
            str(trace_path),
            str(inner_features),
        ],
        capture_output=True,
        text=True,
    )


def _load_trace(trace_path: Path) -> dict:
    """Load trace JSON from file."""
    with open(trace_path, encoding="utf-8") as f:
        return json.load(f)


def _all_steps(trace: dict) -> list[dict]:
    """Flatten all steps from all features/scenarios."""
    return [
        step
        for feature in trace.get("features", [])
        for scenario in feature.get("scenarios", [])
        for step in scenario.get("steps", [])
    ]


def _all_scenarios(trace: dict) -> list[dict]:
    """Flatten all scenarios from all features."""
    return [
        scenario
        for feature in trace.get("features", [])
        for scenario in feature.get("scenarios", [])
    ]


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a simple passing step")
def step_given_passing(context):
    """Prepare to run inner features (already set up in before_all)."""
    context.trace_path = context.tmpdir / "trace_passing.json"


@given("a simple failing step")
def step_given_failing(context):
    """Prepare to run inner features for failing scenario test."""
    context.trace_path = context.tmpdir / "trace_failing.json"


@given("a step with a screenshot attachment")
def step_given_screenshot(context):
    """Prepare to run inner features for screenshot test."""
    context.trace_path = context.tmpdir / "trace_screenshot.json"


@given("a feature with 3 scenarios")
def step_given_stats(context):
    """Prepare to run inner features for stats test."""
    context.trace_path = context.tmpdir / "trace_stats.json"


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the step executes")
def step_when_executes(context):
    """Run behave and generate trace."""
    result = _run_behave(context.inner_features, context.trace_path)
    # Behave exits non-zero when a scenario fails — that's expected
    assert context.trace_path.exists(), (
        f"trace.json not generated.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    context.trace = _load_trace(context.trace_path)


@when("the step executes and fails")
def step_when_executes_fails(context):
    """Run behave (expecting a failing scenario) and generate trace."""
    result = _run_behave(context.inner_features, context.trace_path)
    assert context.trace_path.exists(), (
        f"trace.json not generated.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    context.trace = _load_trace(context.trace_path)


@when("the trace is generated")
def step_when_trace_generated(context):
    """Run behave and generate trace for stats verification."""
    result = _run_behave(context.inner_features, context.trace_path)
    assert context.trace_path.exists(), (
        f"trace.json not generated.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    context.trace = _load_trace(context.trace_path)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then('the trace should contain the step with status "{status}"')
def step_then_status(context, status):
    """Verify trace contains at least one step with the given status."""
    steps = _all_steps(context.trace)
    matching = [s for s in steps if s.get("status") == status]
    assert matching, (
        f"No step with status '{status}' found. Statuses: {[s.get('status') for s in steps]}"
    )
    # Verify duration is non-negative
    for step in matching:
        assert step.get("duration", 0) >= 0, f"Step '{step.get('name')}' has negative duration"


@then('the trace should contain an artifact of type "{artifact_type}"')
def step_then_artifact(context, artifact_type):
    """Verify trace contains at least one artifact of the given type."""
    steps = _all_steps(context.trace)
    found = False
    for step in steps:
        for art in step.get("artifacts", []):
            if art.get("type") == artifact_type:
                found = True
                break
        if found:
            break
    assert found, f"No artifact of type '{artifact_type}' found in any step"


@then("the trace stats should show {count:d} scenarios")
def step_then_stats_scenarios(context, count):
    """Verify trace stats show the expected number of scenarios."""
    stats = context.trace.get("stats", {})
    actual = stats.get("total_scenarios", 0)
    assert actual == count, f"Expected {count} scenarios, got {actual}"


@then("the trace stats should show at least {count:d} steps")
def step_then_stats_steps(context, count):
    """Verify trace stats show at least the expected number of steps."""
    stats = context.trace.get("stats", {})
    actual = stats.get("total_steps", 0)
    assert actual >= count, f"Expected at least {count} steps, got {actual}"


@then("the trace should contain environment info with {field}")
def step_then_env_info(context, field):
    """Verify trace environment contains the given field with a non-empty value."""
    env = context.trace.get("environment", {})
    value = env.get(field, "")
    assert value, f"Environment field '{field}' is empty or missing"


@then("the trace should contain a step with an error message")
def step_then_error(context):
    """Verify at least one failed step has error information."""
    steps = _all_steps(context.trace)
    failed_with_error = [s for s in steps if s.get("status") == "failed" and s.get("error")]
    assert failed_with_error, "No failed step with error information found"
    assert failed_with_error[0]["error"].get("message"), "Error message is empty"
