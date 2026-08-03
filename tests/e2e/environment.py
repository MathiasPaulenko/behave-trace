"""E2E environment for behave-trace meta-tests.

Prepares a temporary directory with inner features, steps, and
environment so each scenario runs in isolation.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path


def before_all(context):
    """Create a temp workspace with inner test features."""
    tmpdir = Path(context.config.userdata.get("e2e_tmpdir", "tmp-e2e"))
    tmpdir.mkdir(exist_ok=True)
    context.tmpdir = tmpdir

    # ── Inner features directory ──
    inner = tmpdir / "inner_features"
    inner.mkdir(exist_ok=True)

    # ── Inner feature file: passing + failing + screenshot ──
    (inner / "simple.feature").write_text(
        textwrap.dedent("""\
        Feature: Inner test feature

          Scenario: A passing scenario
            Given a passing step
            When I do something
            Then I expect success

          Scenario: A failing scenario
            Given a passing step
            When I do something that fails
            Then I expect failure

          Scenario: A scenario with screenshot
            Given a passing step
            When I attach a screenshot
            Then I expect success
        """),
        encoding="utf-8",
    )

    # ── Inner steps ──
    steps_dir = inner / "steps"
    steps_dir.mkdir(exist_ok=True)
    (steps_dir / "steps.py").write_text(
        textwrap.dedent("""\
        import time

        from behave import given, then, when


        @given("a passing step")
        def step_passing(context):
            time.sleep(0.01)


        @when("I do something")
        def step_do(context):
            time.sleep(0.01)


        @then("I expect success")
        def step_success(context):
            assert True


        @when("I do something that fails")
        def step_fail(context):
            time.sleep(0.01)


        @then("I expect failure")
        def step_failure(context):
            assert False, "Intentional failure for E2E test"


        @when("I attach a screenshot")
        def step_attach(context):
            from behave_trace import attach_screenshot
            # 1x1 red PNG (base64)
            png_bytes = bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452"
                "000000010000000108060000001f15c4"
                "890000000d49444154789c63f8cf0000"
                "00030200016dcb24dd0000000049454e"
                "44ae426082"
            )
            attach_screenshot(context, png_bytes, name="test.png")
        """),
        encoding="utf-8",
    )

    # ── Inner environment.py (empty — no hooks needed) ──
    (inner / "environment.py").write_text("", encoding="utf-8")

    context.inner_features = inner


def after_all(context):
    """Clean up temp directory."""
    tmpdir = getattr(context, "tmpdir", None)
    if tmpdir and tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
